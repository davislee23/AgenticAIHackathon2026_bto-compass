# src/extractors.py
import io
from pypdf import PdfReader
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from src.config import get_llm

class PayslipData(BaseModel):
    gross_income: float = Field(default=0.0, description="Gross monthly income in SGD")
    cpf_deduction: float = Field(default=0.0, description="Employee CPF deduction in SGD")
    employment_status: str = Field(default="Unknown", description="Employment status, e.g., Full-time, Part-time")

def extract_income_from_pdf(pdf_bytes: bytes) -> PayslipData:
    """Extracts text from PDF bytes and uses PydanticOutputParser for reliable JSON parsing."""
    # 1. Extract raw text from PDF bytes
    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted_text = ""
    for page in reader.pages:
        extracted_text += page.extract_text() or ""

    # 2. Setup parser and prompt template with format instructions
    parser = PydanticOutputParser(pydantic_object=PayslipData)
    llm = get_llm()

    prompt = PromptTemplate(
        template="""Extract the applicant's monthly gross income, CPF deductions, and employment status from the payslip text below.

PAYSLIP TEXT:
{extracted_text}

{format_instructions}
""",
        input_variables=["extracted_text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    # 3. Execute processing chain
    chain = prompt | llm | parser
    return chain.invoke({"extracted_text": extracted_text})
