import os
import csv
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter

def split_pdf_by_index(pdf_path: str, index_csv_path: str, output_folder: str):
    """
    Split a PDF into separate chapter PDFs based on an index CSV that only provides start pages.
    The CSV must have columns: 'chapter', 'start_page'.
    The end page for each chapter is computed as the page before the start of the next chapter,
    and for the last chapter, it's the last page of the PDF.
    Pages are 1-based.
    Each output file will be prefixed with 'VCR - '.
    """
    # Validate and prepare output folder
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if not os.path.isfile(index_csv_path):
        raise FileNotFoundError(f"Index CSV not found: {index_csv_path}")
    os.makedirs(output_folder, exist_ok=True)

    # Get total number of pages
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
    print(f"Loaded PDF with {total_pages} pages.")

    # Read the index CSV (chapter, start_page)
    chapters = []
    with open(index_csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            chapter = row.get('chapter') or row.get('title') or 'Chapter'
            start = int(row.get('start_page') or row.get('hoja_inicio') or 0)
            if start < 1 or start > total_pages:
                raise ValueError(f"Invalid start page {start} for chapter '{chapter}'.")
            chapters.append((chapter, start))

    # Sort chapters by start page
    chapters.sort(key=lambda x: x[1])

    # Compute page ranges with warnings if overlap
    ranges = []
    for i, (chapter, start) in enumerate(chapters):
        if i < len(chapters) - 1:
            next_start = chapters[i+1][1]
            end = next_start - 1
            if end < start:
                print(
                    f"Warning: next chapter '{chapters[i+1][0]}' starts at page {next_start}, "
                    f"before current '{chapter}' ends at page {start}. Using end = start."
                )
                end = start
        else:
            end = total_pages
        ranges.append((chapter, start, end))

    # Load PDF reader
    reader = PdfReader(pdf_path)

    # Generate individual chapter PDFs
    for chapter, start, end in ranges:
        writer = PdfWriter()
        for page_num in range(start - 1, end):  # zero-based
            writer.add_page(reader.pages[page_num])
        safe_name = ''.join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in chapter).strip()
        filename = f"VCR - {safe_name}.pdf"
        output_path = os.path.join(output_folder, filename)
        with open(output_path, 'wb') as out_f:
            writer.write(out_f)
        print(f"Created chapter PDF: {output_path}")

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(base_dir, "Visa Core Rules.pdf")
    index_csv_path = os.path.join(base_dir, "indice.csv")
    output_folder = os.path.join(base_dir, "chapters")  # sin slash inicial
    split_pdf_by_index(
        pdf_path=pdf_path,
        index_csv_path=index_csv_path,
        output_folder=output_folder
    )


'''
import os
import csv
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter

def split_pdf_by_index(pdf_path: str, index_csv_path: str, output_folder: str):
    """
    Split a PDF into separate chapter PDFs based on an index CSV that only provides start pages.
    The CSV must have columns: 'chapter', 'start_page'.
    The end page for each chapter is computed as the page before the start of the next chapter,
    and for the last chapter, it's the last page of the PDF.
    Pages are 1-based.
    """
    # Validate and prepare output folder
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if not os.path.isfile(index_csv_path):
        raise FileNotFoundError(f"Index CSV not found: {index_csv_path}")
    os.makedirs(output_folder, exist_ok=True)

    # Get total number of pages
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
    print(f"Loaded PDF with {total_pages} pages.")

    # Read the index CSV (chapter, start_page)
    chapters = []
    with open(index_csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            chapter = row.get('chapter') or row.get('title') or 'Chapter'
            start = None
            for key in ('start_page', 'hoja_inicio', 'start'):
                if key in row and row[key].strip():
                    start = int(row[key])
                    break
            if start is None:
                raise ValueError(f"No valid start page found for chapter '{chapter}'.")
            if start < 1 or start > total_pages:
                raise ValueError(f"Invalid start page {start} for chapter '{chapter}'.")
            chapters.append((chapter, start))

    # Sort chapters by start page
    chapters.sort(key=lambda x: x[1])

    # Compute page ranges: end = next_start - 1, last end = total_pages
    ranges = []
    for i, (chapter, start) in enumerate(chapters):
        if i < len(chapters) - 1:
            next_start = chapters[i+1][1]
            end = next_start - 1
            if end < start:
                print(f"Warning: next chapter '{chapters[i+1][0]}' starts at page {next_start}, before current chapter '{chapter}' ends. Setting end = start ({start}).")
                end = start
        else:
            end = total_pages
        ranges.append((chapter, start, end))

    # Load PDF reader
    reader = PdfReader(pdf_path)

    # Generate individual chapter PDFs
    for chapter, start, end in ranges:
        writer = PdfWriter()
        for page_num in range(start - 1, end):  # zero-based
            writer.add_page(reader.pages[page_num])
        safe_name = ''.join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in chapter).strip()
        output_path = os.path.join(output_folder, f"{safe_name}.pdf")
        with open(output_path, 'wb') as out_f:
            writer.write(out_f)
        print(f"Created chapter PDF: {output_path} (pages {start}-{end})")

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(base_dir, "Visa Core Rules.pdf")
    index_csv_path = os.path.join(base_dir, "indice.csv")
    output_folder = os.path.join(base_dir, "chapters")

    
    split_pdf_by_index(
        pdf_path=pdf_path,
        index_csv_path=index_csv_path,
        output_folder=output_folder
    )
    
    
    import argparse
    parser = argparse.ArgumentParser(
        description="Split a PDF into chapters based on an index CSV (chapter, start_page)."
    )
    parser.add_argument('Visa Core Rules', help='Path to the input PDF file')
    parser.add_argument('index_csv', help='Path to the index CSV file')
    parser.add_argument('output_folder', help='Directory to save chapter PDFs')
    args = parser.parse_args()
    split_pdf_by_index(args.pdf_path, args.index_csv, args.output_folder)
'''