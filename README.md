
# Document Processing Solution

A persona-based document analysis system that processes PDF files and extracts relevant sections based on specified roles and tasks.

## Quick Start

### 1. Prepare Input Files

**Add all your PDF files** to the `input/PDF/` directory and **all instruction JSON files** to the `input/` directory:

```
input/
├── PDF/
│   ├── france_cities.pdf
│   ├── france_cuisine.pdf
│   ├── france_hotels.pdf
│   ├── market_report.pdf
│   ├── financial_data.pdf
│   └── ... (all your PDF files)
├── travel_planner.json
├── financial_analysis.json
├── legal_review.json
└── ... (all your instruction JSON files)
```

**Example case:**
- `travel_planner.json` references `france_cities.pdf`, `france_cuisine.pdf`, `france_hotels.pdf`
- `financial_analysis.json` references `market_report.pdf`, `financial_data.pdf`
- The program automatically finds the required PDFs for each JSON file and processes them sequentially

### 2. Build Docker Image

```bash
docker build --platform linux/amd64 -t solution1b:persona-ranker .
```

### 3. Run Processing

 Linux:
```bash
docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none solution1b:persona-ranker
```

Windows:
```bash
docker run --rm -v ${PWD}/input:/app/input -v ${PWD}/output:/app/output --network none solution1b:persona-ranker
```

The program will:
- Process **all JSON files** in the `input/` directory sequentially
- For each JSON file, automatically check and process only the **PDF files specified** in that instruction
- Skip any missing PDFs with a warning (but continue processing other files)

### 4. Check Results

Output files will be generated in the `output/` folder:
```
output/
├── travel_planner_output.json
├── financial_analysis_output.json
├── legal_review_output.json
└── ... (results named by test_case_name)
```

## Instruction File Format

Each JSON file should follow this structure:
```json
{
    "challenge_info": {
        "test_case_name": "your_test_case_name"
    },
    "documents": [
        {"filename": "document1.pdf"},
        {"filename": "document2.pdf"}
    ],
    "persona": {
        "role": "Travel Planner"
    },
    "job_to_be_done": {
        "task": "Plan a 4-day trip for college friends"
    }
}
```

## Requirements

- Docker (no additional dependencies needed)
- Works completely offline
- No network access required during execution

## Notes

- **Sequential Processing**: The system processes all `.json` files in the `input/` directory one by one
- **Selective PDF Usage**: Only PDF files specified in each instruction file are processed (ignores unused PDFs)
- **Automatic File Matching**: The program automatically finds and loads the required PDFs for each JSON instruction
- **Missing File Handling**: Warns about missing PDFs but continues processing other files
- **Output Naming**: Output files are named as `{test_case_name}_output.json`
- **Complete Offline Operation**: Works without network access
