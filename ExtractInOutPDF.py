from pathlib import Path
import shutil
import subprocess
import pymupdf
import pandas as pd
import re

# ===== CONFIG =====

INPUT_FOLDER = "pdfs"
TEMP_FOLDER = "temp_pdfs"
OUTPUT_EXCEL = "output/signals.xlsx"

START_PAGE = 20
END_PAGE = 149

# ==================

input_path = Path(INPUT_FOLDER)
temp_path = Path(TEMP_FOLDER)
# Remove folder completely if it exists
if temp_path.exists():
    shutil.rmtree(temp_path)

# Recreate empty folder
temp_path.mkdir()
output_path = Path("output")
output_path.mkdir(exist_ok=True)

def clean_text(text):
    return " ".join(text.split())

def detect_page_type(page):

    text = page.get_text()

    text_upper = text.upper()

    # INPUT PAGE
    if (
        #"F-DI" in text_upper
        #or " DI" in text_upper
        "ENTRADAS DIGITAIS" in text_upper
        or "ENTRADAS DIGITAIS SEGURAS" in text_upper
        #or "DI" in text_upper
        
    ):
        return "INPUT"

    # OUTPUT PAGE
    if (
        #"DQ" in text_upper
        #or "DO " in text_upper
        "SAIDAS DIGITAIS" in text_upper
        or "SAIDAS DIGITAIS SEGURAS" in text_upper
        #or "DQ" in text_upper

    ):  
        return "OUTPUT"

    return None


def extract_information(page, crop_rect, page_type, doc, page_num, pdf_file):

    results = []
    
    group_texts = page.get_text("blocks", clip=crop_rect)    
    
    for i in range(len(group_texts)):
        signal_name = None
        comment = None
        text = group_texts[i][4].strip().replace(" ", "")
        # remove leading standalone numbers (like "1 DI0")
        text = re.sub(r"^\s*\d+\s*", "", text)

        # extract DI/DQ + number ONLY
        match = re.search(r"\b(?:DI|DQ)(?:\d+|-[A-Z]+\d+)\b", text)

        if match:
            text = match.group(0)

            x = group_texts[i][0]
            y = group_texts[i][1]
            if page_type == "OUTPUT":
                CROP_RECT_SIGNAL = pymupdf.Rect(x - 40, y - 50, x + 40, y - 10)
                signal_name = page.get_text(clip=CROP_RECT_SIGNAL)
            else:
                CROP_RECT_SIGNAL =pymupdf.Rect(x - 40, y + 15, x + 40, y + 63)
                signal_name = page.get_text(clip=CROP_RECT_SIGNAL)
            
            if page_type == "OUTPUT":
                CROP_RECT_COMMENT = pymupdf.Rect(x - 40, y - 90, x + 40, y - 70)
                comment = page.get_text(clip=CROP_RECT_COMMENT).strip()
            else:
                CROP_RECT_COMMENT = pymupdf.Rect(x - 40, y + 80, x + 40, y + 120)
                comment = page.get_text(clip=CROP_RECT_COMMENT).strip()
                           
                           
            # -----------------------------
            # CREATE CROPPED PDF
            # -----------------------------
            temp_doc = pymupdf.open()
            temp_page = temp_doc.new_page(
                width=CROP_RECT_SIGNAL.width,
                height=CROP_RECT_SIGNAL.height
            )
            temp_page.show_pdf_page(
                temp_page.rect,
                doc,
                page_num,
                clip=CROP_RECT_SIGNAL
            )

            temp_pdf_path = temp_path / f"io_{text}_{page_num + 1}.pdf"
            temp_doc.save(str(temp_pdf_path))
            temp_doc.close()
            #print(f"Saved temp PDF: {temp_pdf_path.name}")
            
            #signal_name = signal_name.replace("-", "")
            #print(f"Signal found: {signal_name.strip()} at ({x}, {y}) with comment: {comment} IO: {text}")
        

            results.append({
                "PDF": None,  # To be filled later with the PDF name
                "Page": None,  # To be filled later with the page number
                "Carta": None,  # To be filled later with the component name
                "Signal": signal_name,
                "Comment": comment,
                "IO": text
            })

    return results


def main():
    # ==================
    # Crop rectangle
    # A4 pixels at 300 DPI: 2480 x 3508, at 150 DPI: 1240 x 1754 and at 72 DPI: 595 x 842
    # 1190 x 841 is A4 at 96 DPI, so we can use that as a reference for cropping
    CROP_RECT_Inputs = pymupdf.Rect(50, 625, 1150, 780)
    CROP_RECT_Outputs = pymupdf.Rect(50, 50, 1150, 175)


    pdf_files = list(input_path.glob("*.pdf"))
    
    all_results = []

    for pdf_file in pdf_files:

        print(f"\nProcessing: {pdf_file.name}")

        doc = pymupdf.open(pdf_file)

        #for page_num in range(START_PAGE - 1, len(doc)):
        for page_num in range(START_PAGE - 1, END_PAGE):
            page_type = None
            page = doc[page_num]
            print(page.rect)
            
            page_type = detect_page_type(page)

            if page_type == "INPUT":
                crop_rect = CROP_RECT_Inputs
                page_type = "INPUT"
                print("INPUT PAGE")

            elif page_type == "OUTPUT":
                crop_rect = CROP_RECT_Outputs
                page_type = "OUTPUT"
                print("OUTPUT PAGE")

            else:
                print("Ignoring page")
                continue
            
            # -----------------------------
            # CREATE CROPPED PDF
            # -----------------------------
            temp_doc = pymupdf.open()
            temp_page = temp_doc.new_page(
                width=crop_rect.width,
                height=crop_rect.height
            )
            temp_page.show_pdf_page(
                temp_page.rect,
                doc,
                page_num,
                clip=crop_rect
            )

            temp_pdf_path = temp_path / f"page_{page_num + 1}_{page_type}.pdf"
            temp_doc.save(str(temp_pdf_path))
            temp_doc.close()           
            
            # -----------------------------
            # EXTRACT TEXT FROM CROPPED PAGE
            # -----------------------------
            
            # Get the Name of component
            if page_type == "INPUT":
                component_name = page.get_text(clip=pymupdf.Rect(20, 610, 150, 780))
                component_name = re.search(r"-(\d{3}[A-Z]{2}\d+)", component_name)
                component_name = component_name.group().replace("-", "") if component_name else None
            elif page_type == "OUTPUT":
                component_name = page.get_text(clip=pymupdf.Rect(20, 70, 170, 175))
                component_name = re.search(r"-(\d{3}[A-Z]{2}\d+)", component_name)
                component_name = component_name.group().replace("-", "") if component_name else None
            print(f"Component Name: {component_name if component_name else 'Not found'}")
            

            extracted = extract_information(page, crop_rect, page_type , doc, page_num, pdf_file)

            for row in extracted:
                row["Carta"] = component_name if component_name else "Not found"
                row["PDF"] = pdf_file.name
                row["Page"] = page_num + 1

            all_results.extend(extracted)


            print(f"Processed page {page_num + 1}")


        doc.close()
        
    # -----------------------------
    # EXPORT TO EXCEL
    # -----------------------------

    df = pd.DataFrame(all_results)

    df.to_excel(OUTPUT_EXCEL, index=False)

    print(f"\nExcel saved to: {OUTPUT_EXCEL}")

    print("\nDone ✔")



if __name__ == "__main__":
    main()