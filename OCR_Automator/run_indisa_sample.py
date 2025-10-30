import sys
from pathlib import Path
from process_indisa_unified_v1 import process_pdf_files

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_indisa_sample.py <PDF_PATH> [<PDF_PATH2> ...]")
        sys.exit(1)
    pdfs = [str(Path(p)) for p in sys.argv[1:]]
    out_dir = Path(__file__).resolve().parent / "outputs" / "Indisa" / "web"
    excel, debug = process_pdf_files(pdfs, geocode=False, output_dir=str(out_dir), dpi=300)
    print(f"Excel: {excel}")
    print(f"Debug: {debug}")
