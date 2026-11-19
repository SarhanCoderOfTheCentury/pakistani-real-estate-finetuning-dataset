#!/usr/bin/env python3
"""Stdlib-only validation for the Pakistani real-estate SFT dataset.

Usage: python validate_dataset.py
       python validate_dataset.py --root /path/to/unzipped/folder
Returns 0 only when all automated checks pass. Human semantic review is still needed.
"""
from __future__ import annotations
import argparse, collections, csv, json, re, sys, unicodedata
from pathlib import Path
EXPECTED={'train':2400,'val':300,'test':300}
COLS=['record_id','dataset_split','input_language','property_type','listing_type','extraction_status','quality_review_status']
SCALES={'crore':10_000_000,'cr':10_000_000,'کروڑ':10_000_000,'lakh':100_000,'lac':100_000,'لاکھ':100_000,'thousand':1000,'hazar':1000,'ہزار':1000}
MONEY_RE=re.compile(r'(\d+(?:\.\d+)?)\s*('+'|'.join(sorted(map(re.escape,SCALES),key=len,reverse=True))+r')\b',re.I)
DIGIT_RE=re.compile(r'\bRs\.?\s*([\d,]+)\b',re.I)

def check_schema(val,shape,path,errors):
    if 'anyOf' in shape:
        if not any(not (suberrors:=[]) and check_schema(val,choice,path,suberrors) is None and not suberrors for choice in shape['anyOf']):
            errors.append(f'{path}: value incompatible with all allowed types')
        return
    if 'const' in shape and val!=shape['const']:errors.append(f'{path}: expected constant {shape["const"]!r}')
    types=shape.get('type')
    if types:
        ok={'object':lambda: isinstance(val,dict),'array':lambda: isinstance(val,list),
            'string':lambda: isinstance(val,str),'integer':lambda: isinstance(val,int) and not isinstance(val,bool),
            'number':lambda: (isinstance(val,(int,float)) and not isinstance(val,bool)),
            'boolean':lambda: isinstance(val,bool),'null':lambda: val is None}[types]()
        if not ok:errors.append(f'{path}: expected {types}, got {type(val).__name__}');return
    if 'enum' in shape and val not in shape['enum']:errors.append(f'{path}: invalid enum {val!r}')
    if isinstance(val,str) and len(val)<shape.get('minLength',0):errors.append(f'{path}: empty string forbidden')
    if isinstance(val,(int,float)) and not isinstance(val,bool):
        if 'minimum' in shape and val<shape['minimum']:errors.append(f'{path}: value below minimum')
        if 'exclusiveMinimum' in shape and val<=shape['exclusiveMinimum']:errors.append(f'{path}: value must be positive')
    if isinstance(val,dict):
        props=shape.get('properties',{})
        for key in shape.get('required',[]):
            if key not in val:errors.append(f'{path}.{key}: required key missing')
        if shape.get('additionalProperties') is False:
            for key in set(val)-set(props):errors.append(f'{path}.{key}: unexpected key')
        for key,subschema in props.items():
            if key in val:check_schema(val[key],subschema,path+'.'+key,errors)
    if isinstance(val,list):
        sub=shape.get('items')
        if sub:
            for i,v in enumerate(val):check_schema(v,sub,f'{path}[{i}]',errors)

def parse_price_numeric(phrase):
    """Computes an expressed value in PKR; avoids interpreting bare room/area digits."""
    pairs=MONEY_RE.findall(phrase)
    if pairs:return sum(int(round(float(n)*SCALES[u.lower()])) for n,u in pairs)
    direct=DIGIT_RE.search(phrase)
    if direct:return int(direct.group(1).replace(',',''))
    return None

def normalized_text(s):
    s=unicodedata.normalize('NFKC',s).lower()
    s=re.sub(r'\d+(?:[.,]\d+)*','<n>',s)
    s=re.sub(r'\s+',' ',s)
    return s.strip()

def consistency(input_text,answer,errors,ref):
    p=answer['property'];price=p['price'];desc=input_text
    def err(message):errors.append(f'{ref}: {message}')
    if not desc.strip():err('empty listing description');return
    if price['raw_text'] is not None and price['raw_text'] not in desc:err('price raw_text absent from user description')
    for a in p['area_measurements']:
        if a['raw_text'] not in desc:err('area raw_text absent from user description')
        if not re.search(r'\d',a['raw_text']):err('area lacks numeric quantity')
    for charge in p['additional_charges']:
        if charge['raw_text'] not in desc:err('additional charge raw_text absent from description')
        computed=parse_price_numeric(charge['raw_text'])
        if computed is not None and computed!=charge['amount']:err('additional charge PKR arithmetic mismatch')
    loc=p['location']
    if loc['raw_location_text'] is not None and loc['raw_location_text'] not in desc:err('raw location not in source')
    if loc['city'] is None and loc['province_or_territory'] is not None:err('province filled while city is missing')
    if price['amount'] is not None and any(price[k] is not None for k in ['min_amount','max_amount']):err('amount and range cannot be populated together')
    if price['qualifier']=='range':
        if price['min_amount'] is None or price['max_amount'] is None or price['amount'] is not None:err('range must set only min_amount and max_amount')
        elif price['min_amount']>=price['max_amount']:err('inverted/non-increasing price range')
    elif price['min_amount'] is not None or price['max_amount'] is not None:err('non-range price has min/max')
    if price['amount'] is None and price['min_amount'] is None and price['qualifier']!='unknown':err('qualifier implies amount but none exists')
    if price['currency']!='PKR' and (price['amount'] is not None or price['min_amount'] is not None):err('numeric price without PKR currency')
    if p['listing_type']=='rent' and price['basis']=='total_sale_price':err('rental listing with sale-price basis')
    if p['listing_type']=='sale' and price['basis'] in ['monthly_rent','yearly_rent']:err('sale listing with rental-price basis')
    if p['property_type']=='unknown' and p['property_use']!='unknown':err('unknown property type must have unknown use')
    if p['possession_status']=='file_only' and 'file_only' not in desc.lower() and not any(x in desc.lower() for x in ['file only','file-only','sirf file','صرف فائل']):err('file-only possession without explicit source claim')
    if p['listing_type']=='unknown' and not answer['ambiguities']:err('transaction unknown but no ambiguity documented')
    # Parse currency expressions. Multi-component prices (2 crore 25 lakh) are summed within each range endpoint.
    raw=price['raw_text']
    if raw and price['amount'] is not None:
        computed=parse_price_numeric(raw)
        if computed is not None and computed!=price['amount']:err(f'price arithmetic mismatch {computed} != {price["amount"]}')
    if raw and price['qualifier']=='range':
        parts=re.split(r'\s+to\s+|\s+سے\s+',raw,maxsplit=1)
        if len(parts)==2:
            amounts=[parse_price_numeric(q) for q in parts]
            if amounts[0] is not None and amounts[0]!=price['min_amount']:err('range minimum arithmetic mismatch')
            if amounts[1] is not None and amounts[1]!=price['max_amount']:err('range maximum arithmetic mismatch')
    if answer['extraction_status']=='complete':
        if p['listing_type']=='unknown' or p['property_type']=='unknown' or p['location']['city'] is None or price['amount'] is None and price['min_amount'] is None:err('complete despite unknown principal property attributes')

def validate(root):
    errors=[];schema=json.loads((root/'dataset_schema.json').read_text(encoding='utf-8'))
    system=(root/'system_prompt.txt').read_text(encoding='utf-8').strip()
    seen_exact={}; seen_masked={};rows=[];stats={'language':collections.Counter(),'property_type':collections.Counter(),'listing_type':collections.Counter(),'status':collections.Counter(),'split':collections.Counter()}
    for split,wanted in EXPECTED.items():
        filename=root/f'{split}.jsonl'
        if not filename.is_file():errors.append(f'{filename.name} missing');continue
        count=0
        with filename.open(encoding='utf-8') as f:
            for lineno,line in enumerate(f,1):
                ref=f'{split}.jsonl:{lineno}'
                try:entry=json.loads(line)
                except Exception as ex:errors.append(f'{ref}: outer JSON invalid: {ex}');continue
                if set(entry)!={'messages'}:errors.append(f'{ref}: chat message structure has extra/missing top-level keys');continue
                msgs=entry['messages']
                if not isinstance(msgs,list) or len(msgs)!=3 or [m.get('role') for m in msgs if isinstance(m,dict)]!=['system','user','assistant']:
                    errors.append(f'{ref}: exactly system, user, assistant messages required');continue
                if any(set(m)!={'role','content'} or not isinstance(m['content'],str) for m in msgs):errors.append(f'{ref}: malformed chat message');continue
                if msgs[0]['content']!=system:errors.append(f'{ref}: system instruction does not match system_prompt.txt')
                user_input=msgs[1]['content']
                try:answer=json.loads(msgs[2]['content'])
                except Exception as ex:errors.append(f'{ref}: assistant content not a JSON object: {ex}');continue
                check_schema(answer,schema,'$.assistant',errors)
                if not isinstance(answer,dict) or 'property' not in answer:continue
                consistency(user_input,answer,errors,ref)
                norm=normalized_text(user_input)
                if user_input in seen_exact:errors.append(f'{ref}: duplicate input (first seen {seen_exact[user_input]})')
                seen_exact[user_input]=ref
                if norm in seen_masked and seen_masked[norm][0]!=split:
                    errors.append(f'{ref}: numerical-only paraphrase crosses splits ({seen_masked[norm][1]})')
                seen_masked[norm]=(split,ref)
                count+=1
                p=answer['property']
                stats['language'][answer['input_language']]+=1;stats['property_type'][p['property_type']]+=1
                stats['listing_type'][p['listing_type']]+=1;stats['status'][answer['extraction_status']]+=1;stats['split'][split]+=1
                rows.append((split,answer,user_input))
        if count!=wanted:errors.append(f'{split}.jsonl: expected {wanted}, found {count}')
    mf=root/'dataset_manifest.csv'
    if not mf.is_file():errors.append('dataset_manifest.csv missing')
    else:
        with mf.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if list(reader.fieldnames or [])!=COLS:errors.append('manifest headers do not match expected columns')
            manifest=list(reader)
        if len(manifest)!=sum(EXPECTED.values()):errors.append(f'manifest must contain exactly 3000 records, found {len(manifest)}')
        ids=[m['record_id'] for m in manifest]
        if len(set(ids))!=len(ids):errors.append('non-unique record IDs in manifest')
        for index,((split,answer,_),record) in enumerate(zip(rows,manifest),1):
            p=answer['property']
            expected={'dataset_split':split,'input_language':answer['input_language'],'property_type':p['property_type'],'listing_type':p['listing_type'],'extraction_status':answer['extraction_status']}
            for col,val in expected.items():
                if record[col]!=val:errors.append(f'manifest row {index}: {col} mismatch')
            if record['quality_review_status']!='automated_pass_human_pending':errors.append(f'manifest row {index}: incorrect human review status')
    return errors,stats,len(rows)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);args=ap.parse_args()
    errors,stats,count=validate(args.root)
    report={'validation':'PASS' if not errors else 'FAIL','total_records':count,'expected_records':3000,'errors':errors[:150], 'error_count':len(errors),'counts':{k:dict(v) for k,v in stats.items()},'human_review':'NOT COMPLETED — required before production use'}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if not errors else 1
if __name__=='__main__':raise SystemExit(main())
