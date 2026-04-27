import os
import json
import logging

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

from .models import Product
from .serializers import ProductListSerializer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# POST /api/shop/ai-suggest/
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a fashion stylist assistant for an e-commerce clothing brand.
Your job is to help customers find the perfect clothing items from the store's inventory.

You will receive:
1. A JSON list of all available products (name, category, price, description).
2. The customer's request (occasion, style preference, budget, etc.).

Respond ONLY with a valid JSON object in this exact format (no markdown fences, no extra text):
{
  "message": "<A friendly 1-2 sentence stylist recommendation for the customer>",
  "suggested_slugs": ["<slug1>", "<slug2>", "<slug3>"]
}

Rules:
- suggested_slugs must be slugs from the provided product list only.
- Suggest between 1 and 4 products that best match the customer's request.
- If nothing matches, return an empty suggested_slugs array and explain in the message.
- Keep the message warm, helpful and concise.
"""


def _build_catalogue_context(products):
    """Serialize products into a compact JSON string for the AI prompt."""
    catalogue = []
    for p in products:
        catalogue.append({
            "slug": p.slug,
            "name": p.name,
            "category": p.category.name if p.category else "Uncategorised",
            "price": float(p.price),
            "description": (p.short_description or p.description or "")[:200],
        })
    return json.dumps(catalogue, indent=2)


class AISuggestionView(APIView):
    """
    POST /api/shop/ai-suggest/
    Body: { "query": "casual outfit for a beach party" }
    Returns: { "message": "...", "products": [...ProductListSerializer data] }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        query = request.data.get("query", "").strip()
        if not query:
            return Response(
                {"error": "A 'query' field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        api_key = os.getenv("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", None)
        if not api_key:
            return Response(
                {"error": "AI service is not configured. Please set GOOGLE_API_KEY."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Fetch all in-stock products to feed the AI
        products = list(
            Product.objects
            .select_related("category")
            .prefetch_related("images")
            .filter(stock_quantity__gt=0)
        )
        catalogue_json = _build_catalogue_context(products)

        user_message = (
            f"Available products:\n{catalogue_json}\n\n"
            f"Customer request: {query}"
        )

        # Call Gemini
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=SYSTEM_PROMPT,
            )
            response = model.generate_content(user_message)
            raw = response.text.strip()

            # Strip any accidental markdown fences Gemini might still add
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                raw = raw.rsplit("```", 1)[0].strip()

            ai_data = json.loads(raw)
        except json.JSONDecodeError:
            logger.exception("Gemini returned non-JSON response: %s", raw)
            return Response(
                {"error": "AI returned an unexpected response. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as exc:
            logger.exception("Gemini API error: %s", exc)
            return Response(
                {"error": "AI service is temporarily unavailable."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Resolve suggested slugs → actual products
        suggested_slugs = ai_data.get("suggested_slugs", [])
        slug_to_product = {p.slug: p for p in products}
        matched_products = [
            slug_to_product[slug]
            for slug in suggested_slugs
            if slug in slug_to_product
        ]

        serializer = ProductListSerializer(
            matched_products, many=True, context={"request": request}
        )

        return Response({
            "message": ai_data.get("message", ""),
            "products": serializer.data,
        })
