# Pakistani Real Estate Information Extraction — Synthetic Fine-Tuning Dataset

**Status:** 3,000 synthetic records generated; automated validation **PASS** with **0** reported failures. **Human semantic review has not been completed.**

This package is a supervised fine-tuning (SFT) dataset for a language model that converts free-form Pakistani real-estate advertisements into the **version 1.0 extraction JSON schema**. Inputs cover English, Roman Urdu, Urdu script and mixed English–Roman Urdu, including informal agent and owner messages, abbreviations, prices, area units, missing fields, and contradictory descriptions.

> **Synthetic-data notice:** Every listing, amount, property description and advertised claim in the package was generated for model training. These are **not verified advertisements**, up-to-date price estimates, verified addresses, or confirmations of ownership, NOCs, possession, legal status, facilities or availability. No actual marketplace listings or real contact identities were scraped or included.

## 1. What's inside the ZIP?

| File | Purpose |
|---|---|
| `train.jsonl` | **2,400** SFT chat records for model training (80%). |
| `val.jsonl` | **300** held-out validation chat records (10%). |
| `test.jsonl` | **300** held-out test chat records (10%). Do not train on this split. |
| `system_prompt.txt` | The **exact system message** repeated in each of the 3,000 chat examples. |
| `examples.xlsx` | A readable **60-record sample**, with the original description and target JSON, plus an overview and guide. It is for browsing, **not an additional training split**. |
| `dataset_schema.json` | Machine-readable JSON Schema (Draft 2020-12) defining all output keys, field types and enums. |
| `dataset_manifest.csv` | One metadata row per record with record ID, split, language, property type, transaction, extraction status and review status. The manifest is **not** part of the model prompts. |
| `validate_dataset.py` | Standard-library-only validation for JSONL records, exact schema, enums, numeric consistency, raw text, duplicate inputs, split sizes and manifest alignment. |
| `README.md` | Project, usage, statistics, validation details and caveats (this file). |

Directory layout:

```text
pakistani-real-estate-finetuning-dataset/
├── examples.xlsx
├── system_prompt.txt
├── train.jsonl
├── val.jsonl
├── test.jsonl
├── dataset_schema.json
├── dataset_manifest.csv
├── validate_dataset.py
└── README.md
```

## 2. Actual split sizes

| Split | Records | Percentage |
|---|---:|---:|
| Training | 2,400 | 80% |
| Validation | 300 | 10% |
| Test | 300 | 10% |
| **Total** | **3,000** | **100%** |

All JSONL entries use one unique property description and the same system instruction.

## 3. Actual dataset statistics

### Input-language distribution

| Language | Count | Share |
|---|---:|---:|
| `roman_urdu` | 1,050 | 35.0% |
| `english` | 750 | 25.0% |
| `mixed` | 750 | 25.0% |
| `urdu_script` | 450 | 15.0% |

### Transaction type distribution (extracted labels)

| Listing type | Count | Share |
|---|---:|---:|
| `sale` | 1,580 | 52.7% |
| `rent` | 1,007 | 33.6% |
| `lease` | 293 | 9.8% |
| `unknown` | 120 | 4.0% |

The target *generation* proportions were 55% sale, 35% rent and 10% lease. Deliberately ambiguous or unspecified advertisements were annotated with `listing_type: "unknown"` instead of inventing a transaction; therefore the **actual annotated output** has the distribution shown above.

### Property-type distribution (extracted labels)

| Property type | Count | Share |
|---|---:|---:|
| `portion` | 454 | 15.1% |
| `plot` | 450 | 15.0% |
| `warehouse` | 228 | 7.6% |
| `office` | 226 | 7.5% |
| `building` | 225 | 7.5% |
| `flat_apartment` | 224 | 7.5% |
| `industrial_property` | 224 | 7.5% |
| `agricultural_land` | 223 | 7.4% |
| `house` | 222 | 7.4% |
| `farmhouse` | 222 | 7.4% |
| `shop` | 221 | 7.4% |
| `unknown` | 81 | 2.7% |

The `plot` count combines residential and commercial plot variants; `portion` combines upper and lower portions. The rare `unknown` type is intentional, for incomplete listings where the category is not supported by the input.

### Extraction completeness

| Extraction status | Count | Share |
|---|---:|---:|
| `complete` | 1,980 | 66.0% |
| `partial` | 1,020 | 34.0% |

### Additional coverage checks

| Property / condition | Records |
|---|---:|
| With explicitly stated city | 2,666 |
| With one or more area measurements | 2,760 |
| With parseable numeric listing price | 2,372 |
| With additional charges | 529 |
| With utility information | 2,014 |
| With unresolved bedroom conflict | 46 |

Descriptions average **218.5 characters**; shortest **64**, longest **439**. Records reference 15 selected Pakistani cities, with missing-city cases intentionally retained.

## 4. What does one JSONL training record look like?

Each line in `train.jsonl`, `val.jsonl`, or `test.jsonl` is **one JSON object** with exactly three chat messages:

```json
{
  "messages": [
    {"role": "system", "content": "<the exact contents of system_prompt.txt>"},
    {"role": "user", "content": "5 marla house for sale in Lahore, demand 85 lakh."},
    {"role": "assistant", "content": "{\"task\":\"pakistani_property_listing_extraction\",...}"}
  ]
}
```

*This is a shortened format illustration, not one of the actual records.* **Assistant `content` is a JSON-encoded string**, not a nested object. The actual files include all required extraction fields; inspect `examples.xlsx` to see complete examples.

The model input is the **user description** and the model output is the **assistant JSON string**. The system prompt is identical for every record.

## 5. Target extraction structure

Version 1.0 of the JSON response contains only:

```text
task
schema_version
extraction_status
input_language
property
  listing_type
  property_type
  property_subtype
  property_use
  location: country, province_or_territory, city, district, locality,
            housing_scheme_or_project, phase, block_or_sector,
            street_or_plot_number, nearby_landmark, raw_location_text
  area_measurements[]: kind, value, unit, raw_text
  price: amount, min_amount, max_amount, currency, basis,
         qualifier, negotiable, raw_text
  additional_charges[]: type, amount, currency, raw_text
  building_details: bedrooms, bathrooms, kitchens, living_rooms,
                    floor_number, total_floors, parking_spaces, furnishing
  features[]
  utilities: electricity, gas, water, sewerage
  possession_status
  document_terms[]
  availability_status
  additional_details[]
ambiguities[]
```

**Missing-value conventions:** missing scalar properties are JSON `null`, missing collections are `[]`, and missing enum states use `unknown` / `not_stated` as defined in the formal schema. Contradictions are preserved in `ambiguities`; affected attributes are left unresolved. Negative claims (such as *gas nahi*, *not a corner plot*) must not become positive facts.

**Money:** Pakistani expressions such as lakh / lac / crore / hazar are converted to integer PKR values when clear. Ranges use `min_amount`/`max_amount` and `amount: null`; a separately stated security deposit, advance payment or commission is placed in `additional_charges`.

**Areas:** original values and units are retained exactly (marla, kanal, square feet, square yards, gaz, acres, hectares). The model must not silently convert marla, kanal or gaz using a universal assumption; it must keep plot, land and covered area apart.

**Legal terms:** any mentions of `registry`, `intiqal`, `NOC` or `dues clear` are **claims made by the synthetic advertiser** rather than verified facts.

## 6. How to validate the package

Unzip the archive, open a terminal inside the dataset folder and run:

```bash
python validate_dataset.py
```

Or from elsewhere:

```bash
python validate_dataset.py --root /path/to/pakistani-real-estate-finetuning-dataset
```

No external Python packages are required for this validator. It checks the following:

1. That all 3 JSONL files parse successfully, contain the required chat turns and use the exact common system prompt.
2. That assistant content parses as an object and satisfies the full strict JSON Schema for required fields, types and enums (implemented directly in Python, without needing `jsonschema`).
3. Correct split counts (2,400 / 300 / 300), uniqueness of input strings and number-masked near-identical input descriptions across splits.
4. Presence of raw quoted location, area, price and separate charges in the corresponding source input; basic PKR arithmetic checks for supported formatted amounts.
5. Price range consistency, missing-value rules for principal fields, transaction/price-basis consistency, source presence of file-only possession, and manifest alignment/unique IDs.

**Last completed automated run:** `PASS`, **3,000** valid records, **0** reported errors. The validator exits with code `0` on success and nonzero on failure. It does **not** verify every possible linguistic inference or substitute for independent expert annotation review.

## 7. Example fine-tuning workflow

1. Decide on a chat fine-tuning provider/model that accepts JSONL chat records with `system`, `user`, `assistant` roles. Check the provider's current format/size limits; **this dataset is a generic chat SFT format and is not guaranteed compatible with every provider without adaptation**.
2. Run the validator and **conduct human semantic QA** on a stratified sample across all languages, cities, property categories, ambiguities and missing-field cases. Correct any mistakes before training.
3. Use `train.jsonl` for training. Use `val.jsonl` for model-selection and tuning decisions. Keep `test.jsonl` locked until the final evaluation.
4. At inference, send the system prompt from `system_prompt.txt` followed by a new unstructured property listing. Require a JSON response matching `dataset_schema.json`.
5. Evaluate **field-level precision/recall**, price-normalization accuracy, extraction-only behavior, exact schema validity and hallucination rate by input language and property type. A valid JSON response can still contain inaccurate facts.

Example local Python inspection:

```python
import json
from pathlib import Path

record = json.loads(Path("train.jsonl").open(encoding="utf-8").readline())
listing = record["messages"][1]["content"]
target = json.loads(record["messages"][2]["content"])
print("Input:", listing)
print("Target type:", target["property"]["property_type"])
```

## 8. Data quality and known limitations

- All values and examples are synthetic and **should not** be used for property price estimation, valuation, real-estate investment decisions, legal due diligence or live availability checks.
- The automated generator uses compositional sentence patterns and local language phrases; some examples may be stylistically repetitive or imperfectly idiomatic. Roman Urdu orthography is not standardized, and the Urdu-script examples may require native-speaker review.
- Locations are selected from widely used city/locality labels, but **no individual property address or association was independently verified**. Do not treat an example as proof of a physical property.
- Some text may intentionally omit a price, city, transaction or property type. `unknown` and `partial` annotations are by design; exact desired sale/rent/lease percentages are therefore not equal to the observed output labels.
- The generation process rejected exact duplicates and repeated underlying structured listing signatures that changed only a price. The shipped validator additionally checks number-masked text collisions across splits. **No automatic method can guarantee that every semantically near-identical paraphrase has been eliminated.**
- **Human review: pending for all records.** The manifest has `quality_review_status=automated_pass_human_pending`. Passing schema validation and programmatic consistency checks is not evidence that all 3,000 multilingual assistant labels are independently correct.

## 9. Manifest fields

The manifest columns are `record_id`, `dataset_split`, `input_language`, `property_type`, `listing_type`, `extraction_status`, `quality_review_status`. Record IDs run from `PKRE-000001` to `PKRE-003000` in the same order as the three JSONL files (train, val, test). They do not appear in any fine-tuning prompt.

## 10. Suggested next action

Before training, have a qualified annotator review at least a stratified sample from each language and all edge-case categories; fix errors, re-run the included validator, and only then benchmark the model on the held-out test split.
