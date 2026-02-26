"""AI services API endpoints - NLP parser, receipt scanner, chatbot, insights."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.config import get_settings
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["AI Services"])

settings = get_settings()


class ParseExpenseRequest(BaseModel):
    text: str


class ParsedExpense(BaseModel):
    description: str = ""
    amount: float = 0
    paid_by: str = ""
    category: str = "general"
    participants: list[str] = []
    confidence: float = 0


class ChatRequest(BaseModel):
    message: str
    group_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    suggestions: list[str] = []


class InsightResponse(BaseModel):
    summary: str
    top_category: str = ""
    total_spending: float = 0
    tips: list[str] = []


@router.post("/parse-expense", response_model=ParsedExpense)
async def parse_expense(
    data: ParseExpenseRequest,
    current_user: User = Depends(get_current_user),
):
    """Parse natural language into structured expense data using Gemini AI."""
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your-gemini-api-key-here":
        # Fallback: simple rule-based parsing
        return _simple_parse(data.text)

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        prompt = f"""Parse this expense description into structured data. Return JSON only, no markdown.
Text: "{data.text}"

Return this exact JSON format:
{{"description": "what was purchased", "amount": 0.00, "paid_by": "person name", "category": "food/transport/entertainment/shopping/utilities/general", "participants": ["name1", "name2"], "confidence": 0.0-1.0}}

If you can't determine a field, use empty string or 0. For confidence, rate how confident you are in the parsing."""

        response = model.generate_content(prompt)
        import json
        text = response.text.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        return ParsedExpense(**parsed)
    except Exception as e:
        # Fallback to simple parsing
        return _simple_parse(data.text)


def _simple_parse(text: str) -> ParsedExpense:
    """Simple rule-based expense parser fallback."""
    import re
    amount_match = re.search(r'\$?([\d,]+\.?\d*)', text)
    amount = float(amount_match.group(1).replace(',', '')) if amount_match else 0

    # Try to detect category
    category = "general"
    categories_map = {
        "food": ["dinner", "lunch", "breakfast", "coffee", "restaurant", "pizza", "food", "meal", "drinks"],
        "transport": ["uber", "lyft", "taxi", "gas", "fuel", "bus", "train", "flight", "parking"],
        "entertainment": ["movie", "concert", "game", "show", "tickets", "netflix"],
        "shopping": ["amazon", "store", "shop", "buy", "bought", "purchase"],
        "utilities": ["electricity", "water", "internet", "phone", "rent", "bill"],
    }
    text_lower = text.lower()
    for cat, keywords in categories_map.items():
        if any(kw in text_lower for kw in keywords):
            category = cat
            break

    # Try to detect who paid
    paid_by = ""
    paid_patterns = [r'(\w+)\s+paid', r'(\w+)\s+bought', r'(\w+)\s+spent']
    for pattern in paid_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            paid_by = match.group(1)
            break

    # Clean description
    description = re.sub(r'\$[\d,]+\.?\d*', '', text).strip()
    description = re.sub(r'\s+', ' ', description)

    return ParsedExpense(
        description=description or text,
        amount=amount,
        paid_by=paid_by,
        category=category,
        confidence=0.4 if amount > 0 else 0.1,
    )


@router.post("/scan-receipt")
async def scan_receipt(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Scan a receipt image using OCR and AI to extract expense data."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file")

    contents = await file.read()

    # Try Gemini Vision first
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your-gemini-api-key-here":
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)

            import PIL.Image
            import io
            image = PIL.Image.open(io.BytesIO(contents))

            prompt = """Analyze this receipt image. Extract the following in JSON format:
{"items": [{"name": "item name", "amount": 0.00}], "total": 0.00, "vendor": "store name", "date": "YYYY-MM-DD", "category": "food/shopping/transport/utilities/general"}

Return ONLY valid JSON, no markdown."""

            response = model.generate_content([prompt, image])
            import json
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(text)
        except Exception:
            pass

    # Fallback: Tesseract OCR
    try:
        import pytesseract
        import PIL.Image
        import io
        image = PIL.Image.open(io.BytesIO(contents))
        ocr_text = pytesseract.image_to_string(image)

        # Basic extraction
        import re
        amounts = re.findall(r'\$?([\d]+\.[\d]{2})', ocr_text)
        total = float(max(amounts, key=float)) if amounts else 0

        return {
            "items": [],
            "total": total,
            "vendor": "",
            "date": "",
            "category": "general",
            "raw_text": ocr_text[:500],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat with the AI assistant about expenses and groups."""
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your-gemini-api-key-here":
        return ChatResponse(
            reply="AI assistant requires a Gemini API key. Please set GEMINI_API_KEY in your .env file.",
            suggestions=["Set up your Gemini API key", "Try the expense parser instead"],
        )

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        system_prompt = """You are a helpful expense-splitting assistant. You help users:
- Track and split expenses fairly
- Understand their spending patterns
- Get suggestions for budget optimization
- Resolve questions about who owes what

Be concise, friendly, and helpful. If the user describes an expense, extract the details.
Format currency values properly. Keep responses under 200 words."""

        response = model.generate_content(f"{system_prompt}\n\nUser: {data.message}")
        reply = response.text.strip()

        return ChatResponse(
            reply=reply,
            suggestions=["Add an expense", "Show balances", "Settle up"],
        )
    except Exception as e:
        return ChatResponse(
            reply=f"Sorry, I encountered an issue: {str(e)}",
            suggestions=["Try again", "Check your API key"],
        )


@router.get("/insights/{group_id}", response_model=InsightResponse)
async def get_insights(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get AI-powered spending insights for a group."""
    from sqlalchemy import select, func
    from app.models.expense import Expense
    from app.models.group import GroupMember

    # Verify membership
    member_check = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
        )
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not a member of this group")

    # Get expense stats
    result = await db.execute(
        select(
            func.count(Expense.id),
            func.sum(Expense.amount),
        ).where(Expense.group_id == group_id)
    )
    row = result.first()
    expense_count = row[0] or 0
    total_spending = row[1] or 0

    # Get top category
    cat_result = await db.execute(
        select(Expense.category, func.sum(Expense.amount).label("total"))
        .where(Expense.group_id == group_id)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
        .limit(1)
    )
    top_cat_row = cat_result.first()
    top_category = top_cat_row[0] if top_cat_row else "none"

    summary = f"Total of {expense_count} expenses worth ${total_spending:.2f}."
    if top_category != "none":
        summary += f" Top category: {top_category}."

    tips = []
    if total_spending > 1000:
        tips.append("Consider setting a monthly budget for your group")
    if expense_count > 20:
        tips.append("You have many expenses — try settling up regularly")
    tips.append("Use the AI parser to add expenses quickly by typing naturally")

    return InsightResponse(
        summary=summary,
        top_category=top_category,
        total_spending=round(total_spending, 2),
        tips=tips,
    )
