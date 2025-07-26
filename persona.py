import os
import json
import re
from datetime import datetime
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer, util
from typing import List, Dict, Tuple

PDF_INPUT_DIR = "./input/PDF"
INSTRUCTION_DIR = "./input"
OUTPUT_DIR = "./output"
MODEL_PATH = "./model/all-MiniLM-L6-v2"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load model on CPU
model = SentenceTransformer(MODEL_PATH, device='cpu')

def find_instruction_files() -> List[str]:
    """Find all JSON instruction files in the input directory"""
    instruction_files = []
    
    for file in os.listdir(INSTRUCTION_DIR):
        if file.lower().endswith('.json'):
            file_path = os.path.join(INSTRUCTION_DIR, file)
            instruction_files.append(file_path)
    
    return sorted(instruction_files)  # Sort for consistent processing order

def read_instruction(instruction_path: str):
    """Read instruction file and extract persona and job information"""
    if not os.path.isfile(instruction_path):
        raise FileNotFoundError(f"Instruction JSON file not found: {instruction_path}")
    
    with open(instruction_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    persona = data.get("persona", {}).get("role", "Researcher")
    job = data.get("job_to_be_done", {}).get("task", "Analyze documents")
    documents = data.get("documents", [])
    challenge_info = data.get("challenge_info", {})
    test_case_name = challenge_info.get("test_case_name", "output")
    
    return persona, job, documents, challenge_info, test_case_name

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file"""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ""

def split_into_sections(text: str, filename: str) -> List[Dict]:
    """Split text into sections based on headings and content structure"""
    sections = []
    
    # Split by potential section markers (lines that look like headings)
    lines = text.split('\n')
    current_section = []
    current_title = None
    page_counter = 1
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Detect potential section headers (all caps, or title case with few words)
        is_header = (
            len(line.split()) <= 6 and 
            (line.isupper() or line.istitle()) and 
            len(line) > 5 and
            not line.endswith('.') and
            not line.startswith('•')
        )
        
        if is_header and current_section:
            # Save previous section
            section_text = ' '.join(current_section).strip()
            if section_text and len(section_text) > 100:  # Only keep substantial sections
                sections.append({
                    'title': current_title or f"Section {len(sections) + 1}",
                    'text': section_text,
                    'page': page_counter,
                    'filename': filename
                })
            current_section = []
            current_title = line
            page_counter += 1
        else:
            current_section.append(line)
    
    # Add the last section
    if current_section:
        section_text = ' '.join(current_section).strip()
        if section_text and len(section_text) > 100:
            sections.append({
                'title': current_title or f"Section {len(sections) + 1}",
                'text': section_text,
                'page': page_counter,
                'filename': filename
            })
    
    return sections

def rank_sections_by_relevance(sections: List[Dict], persona: str, job: str) -> List[Dict]:
    """Rank sections by relevance to the persona and job"""
    query = f"Persona: {persona}. Task: {job}."
    query_embedding = model.encode(query, convert_to_tensor=True, device='cpu')
    
    scored_sections = []
    
    for section in sections:
        # Use title + first part of text for similarity
        section_repr = f"{section['title']} {section['text'][:500]}"
        section_embedding = model.encode(section_repr, convert_to_tensor=True, device='cpu')
        similarity = util.pytorch_cos_sim(query_embedding, section_embedding).item()
        
        scored_sections.append({
            **section,
            'similarity_score': similarity
        })
    
    # Sort by similarity score (descending)
    return sorted(scored_sections, key=lambda x: x['similarity_score'], reverse=True)

def select_top_sections(ranked_sections: List[Dict], max_sections: int = 5) -> List[Dict]:
    """Select top sections ensuring diversity across documents"""
    selected = []
    used_documents = set()
    
    # First pass: select highest scoring section from each document
    for section in ranked_sections:
        if section['filename'] not in used_documents and len(selected) < max_sections:
            selected.append(section)
            used_documents.add(section['filename'])
    
    # Second pass: fill remaining slots with highest scoring sections
    for section in ranked_sections:
        if len(selected) >= max_sections:
            break
        if section not in selected:
            selected.append(section)
    
    return selected[:max_sections]

def refine_section_text(text: str, max_length: int = 800) -> str:
    """Refine and truncate section text to be more focused"""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    
    refined_text = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        if len(refined_text + sentence) > max_length:
            break
        refined_text += sentence + ". "
    
    return refined_text.strip()

def process_single_instruction(instruction_path: str) -> bool:
    """Process a single instruction file"""
    try:
        instruction_filename = os.path.basename(instruction_path)
        print(f"\n{'='*60}")
        print(f"📄 Processing instruction file: {instruction_filename}")
        print(f"{'='*60}")
        
        persona, job, document_list, challenge_info, test_case_name = read_instruction(instruction_path)
        print(f"🔹 Persona: {persona}")
        print(f"🔹 Job: {job}")
        print(f"🔹 Test Case: {test_case_name}")
        
        # Load and process all PDFs
        all_sections = []
        processed_documents = []
        
        for doc_info in document_list:
            filename = doc_info['filename']
            pdf_path = os.path.join(PDF_INPUT_DIR, filename)
            
            if not os.path.exists(pdf_path):
                print(f"⚠️  Warning: {filename} not found")
                continue
                
            print(f"📖 Processing: {filename}")
            text = extract_text_from_pdf(pdf_path)
            
            if text:
                sections = split_into_sections(text, filename)
                all_sections.extend(sections)
                processed_documents.append(filename)
        
        if not all_sections:
            print("❌ No sections found in any documents")
            return False
        
        # Rank sections by relevance
        ranked_sections = rank_sections_by_relevance(all_sections, persona, job)
        
        # Select top sections
        top_sections = select_top_sections(ranked_sections, max_sections=5)
        
        # Create output structure
        output = {
            "metadata": {
                "input_documents": processed_documents,
                "persona": persona,
                "job_to_be_done": job,
                "processing_timestamp": datetime.now().isoformat()
            },
            "extracted_sections": [],
            "subsection_analysis": []
        }
        
        # Add extracted sections
        for i, section in enumerate(top_sections):
            output["extracted_sections"].append({
                "document": section['filename'],
                "section_title": section['title'],
                "importance_rank": i + 1,
                "page_number": section['page']
            })
            
            # Add subsection analysis
            refined_text = refine_section_text(section['text'])
            output["subsection_analysis"].append({
                "document": section['filename'],
                "refined_text": refined_text,
                "page_number": section['page']
            })
        
        # Save output with dynamic filename based on test_case_name
        output_filename = f"{test_case_name}_output.json"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        
        print(f"✅ Output saved to: {output_path}")
        print(f"📊 Processed {len(all_sections)} sections from {len(processed_documents)} documents")
        print(f"🎯 Selected top {len(top_sections)} most relevant sections")
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing {instruction_path}: {e}")
        import traceback
        traceback.print_exc()
        return False

def process_documents():
    """Main processing function - handles multiple instruction files"""
    instruction_files = find_instruction_files()
    
    if not instruction_files:
        print("❌ No JSON instruction files found in input directory")
        return
    
    print(f"🔍 Found {len(instruction_files)} instruction file(s)")
    for file_path in instruction_files:
        print(f"   - {os.path.basename(file_path)}")
    
    successful_count = 0
    failed_count = 0
    
    for instruction_path in instruction_files:
        success = process_single_instruction(instruction_path)
        if success:
            successful_count += 1
        else:
            failed_count += 1
    
    print(f"\n{'='*60}")
    print(f"🏁 BATCH PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"✅ Successfully processed: {successful_count} file(s)")
    print(f"❌ Failed to process: {failed_count} file(s)")
    print(f"📁 Total instruction files: {len(instruction_files)}")
    
    if successful_count > 0:
        print(f"📂 Output files saved in: {OUTPUT_DIR}")
    
    return successful_count, failed_count

def main():
    try:
        process_documents()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()