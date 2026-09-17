from fastapi import APIRouter, HTTPException
import stripe
import os

router = APIRouter(prefix="/stripe")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create-checkout-session")
async def create_checkout_session(payload: dict):
    try:
        price_id = payload["priceId"]
        user_id = payload["userId"]

        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            success_url=f"{os.getenv('FRONTEND_URL')}/billing?success=1",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/billing?canceled=1",
            metadata={"userId": user_id}
        )

        return {"url": session.url}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
