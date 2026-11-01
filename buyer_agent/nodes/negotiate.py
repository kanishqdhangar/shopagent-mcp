import time

from audit import write_audit_log
from state import AgentState, DecisionLogEntry
from tools.mcp_tools import apply_discount


async def negotiate(state: AgentState) -> dict:
    started = time.perf_counter()
    product = state.get("chosen_product")
    action = state.get("negotiation_action") or {}
    history = list(state.get("negotiation_history", []))
    log = list(state.get("decision_log", []))

    def record(decision: str, reason: str, result: dict | None = None) -> dict:
        entry = DecisionLogEntry(step="negotiation", decision=decision, reason=reason,
                                 tokens_used=0, latency_ms=int((time.perf_counter() - started) * 1000))
        return {"decision_log": [*log, entry]}

    if action.get("action") == "cancel":
        history.append({"status": "cancelled"})
        await write_audit_log(run_id=state["run_id"], node_name="negotiation", decision="Negotiation cancelled", reasoning="User cancelled the active negotiation.", tokens_used=0, latency_ms=int((time.perf_counter() - started) * 1000))
        return {**record("Negotiation cancelled", "User cancelled the negotiation."),
                "negotiation_status": "cancelled", "pending_negotiation": None,
                "negotiation_history": history, "negotiation_requested": False}

    if action.get("action") == "reject":
        history.append({"status": "rejected"})
        await write_audit_log(run_id=state["run_id"], node_name="negotiation", decision="Offer rejected", reasoning="User rejected the active seller offer.", tokens_used=0, latency_ms=int((time.perf_counter() - started) * 1000))
        return {**record("Offer rejected", "User rejected the current offer."),
                "negotiation_status": "rejected", "pending_negotiation": None,
                "negotiation_history": history, "negotiation_requested": False}

    if action.get("action") == "accept":
        pending = state.get("pending_negotiation") or {}
        if (not pending or pending.get("product_id") != str((product or {}).get("id"))
                or pending.get("status") not in ("pending", "maximum_reached", "accepted")):
            return {**record("Offer unavailable", "There is no current offer for this product."),
                    "negotiation_status": "expired", "failure_reason": "negotiation_offer_unavailable"}
        accepted = {**pending, "status": "accepted"}
        history.append({"status": "accepted", "discount_percent": pending.get("discount_percent"),
                        "price": pending.get("discounted_price")})
        await write_audit_log(run_id=state["run_id"], node_name="negotiation", decision="Offer accepted", reasoning=f"User accepted seller offer for product {product.get('id')} at ₹{float(pending.get('discounted_price') or 0):.2f}; checkout remains separately authorized.", tokens_used=0, latency_ms=int((time.perf_counter() - started) * 1000))
        authorized = bool(action.get("purchase_authorized"))
        return {**record("Offer accepted", "User accepted seller-validated offer; checkout requires explicit buy intent."),
                "negotiation_status": "accepted", "pending_negotiation": accepted,
                "negotiation_history": history, "purchase_authorized": authorized,
                "request_kind": "checkout_accepted" if authorized else "negotiation_complete"}

    if not product or not product.get("id"):
        return {**record("Negotiation unavailable", "No product was selected for this negotiation."),
                "negotiation_status": "unavailable", "failure_reason": "negotiation_product_unavailable"}

    arguments = {"product_id": str(product["id"])}
    if action.get("action") == "request_percent":
        arguments["percent"] = action.get("requested_discount_percent")
    elif action.get("action") == "request_target_price":
        arguments["target_price"] = action.get("target_price")
    elif action.get("action") == "request_best":
        arguments["best_price"] = True
    else:
        return {**record("Negotiation not recognized", "Message did not contain a supported negotiation action."),
                "negotiation_status": "unavailable"}

    previous = state.get("pending_negotiation") or {}
    if previous.get("product_id") == str(product["id"]):
        arguments["expected_original_price"] = previous.get("original_price")
    try:
        quote = await apply_discount(**arguments)
    except Exception as exc:
        reason = f"Seller quote validation failed: {exc}"
        await write_audit_log(run_id=state["run_id"], node_name="negotiation", decision="Seller quote failed", reasoning=reason, tokens_used=0, latency_ms=int((time.perf_counter() - started) * 1000))
        return {**record("Seller quote failed", reason), "negotiation_status": "failed", "failure_reason": "negotiation_quote_failed"}

    if not quote.get("applied"):
        offer = quote.get("best_allowed_offer")
        status = "maximum_reached" if offer else "rejected"
        history.append({"status": status, "requested_discount_percent": quote.get("requested_discount_percent"),
                        "reason": quote.get("rejection_reason"), "best_allowed_offer": offer})
        reason = quote.get("rejection_reason") or "Seller rejected the requested offer."
        await write_audit_log(run_id=state["run_id"], node_name="negotiation", decision="Discount rejected", reasoning=reason, tokens_used=0, latency_ms=int((time.perf_counter() - started) * 1000))
        return {**record("Discount rejected", reason), "negotiation_status": status,
                "negotiation_product_id": str(product["id"]), "original_price": quote.get("original_price"),
                "requested_discount_percent": quote.get("requested_discount_percent"),
                "pending_negotiation": ({"product_id": str(product["id"]), "product_name": product.get("name"),
                    "original_price": quote.get("original_price"), "discount_percent": offer["discount_percent"],
                    "discounted_price": offer["discounted_price"], "status": status,
                    "maximum_discount_percent": quote.get("maximum_discount_percent"),
                    "rejection_reason": reason} if offer else {"product_id": str(product["id"]),
                    "product_name": product.get("name"), "original_price": quote.get("original_price"),
                    "discount_percent": 0, "discounted_price": quote.get("original_price"),
                    "status": "rejected", "rejection_reason": reason}),
                "negotiation_history": history, "negotiation_attempts": state.get("negotiation_attempts", 0) + 1}

    if float(quote.get("applied_discount_percent", 0)) == 0:
        status = "no_discount"
    else:
        status = "pending"
    offer = {"product_id": str(product["id"]), "product_name": product.get("name"),
             "original_price": quote["original_price"], "discount_percent": quote["applied_discount_percent"],
             "discounted_price": quote["discounted_price"], "status": status,
             "maximum_discount_percent": quote.get("maximum_discount_percent")}
    history.append({"status": status, "discount_percent": offer["discount_percent"], "price": offer["discounted_price"]})
    await write_audit_log(run_id=state["run_id"], node_name="negotiation", decision="Seller discount approved", reasoning=f"Seller approved {offer['discount_percent']:.2f}% for product {product['id']} at ₹{offer['discounted_price']:.2f}.", tokens_used=0, latency_ms=int((time.perf_counter() - started) * 1000))
    return {**record("Seller discount approved" if status == "pending" else "No discount offered", f"Seller validated {offer['discount_percent']:.2f}% against catalog price."),
            "negotiation_status": status, "negotiation_product_id": str(product["id"]),
            "original_price": quote["original_price"], "requested_discount_percent": quote.get("requested_discount_percent"),
            "offered_discount_percent": quote["applied_discount_percent"],
            "negotiated_price": quote["discounted_price"], "pending_negotiation": offer,
            "negotiation_history": history, "negotiation_attempts": state.get("negotiation_attempts", 0) + 1,
            "failure_reason": None}


async def validate_negotiation(state: AgentState) -> dict:
    offer = state.get("pending_negotiation") or {}
    product = state.get("chosen_product") or {}
    if (state.get("negotiation_status") != "accepted" or offer.get("status") != "accepted"
            or offer.get("product_id") != str(product.get("id"))):
        return {"failure_reason": "negotiation_validation_failed"}
    try:
        result = await apply_discount(product_id=str(product["id"]), percent=offer.get("discount_percent"),
                                      expected_original_price=offer.get("original_price"))
    except Exception as exc:
        return {"failure_reason": f"negotiation_revalidation_failed: {exc}"}
    if not result.get("applied"):
        await write_audit_log(run_id=state["run_id"], node_name="negotiation", decision="Accepted offer failed revalidation", reasoning="Seller rejected the offer during final price revalidation.", tokens_used=0, latency_ms=0)
        return {"failure_reason": "negotiation_revalidation_failed"}
    await write_audit_log(run_id=state["run_id"], node_name="negotiation", decision="Final offer revalidated", reasoning=f"Seller revalidated product {product['id']} at ₹{result['discounted_price']:.2f} before checkout.", tokens_used=0, latency_ms=0)
    return {"original_price": result["original_price"], "offered_discount_percent": result["applied_discount_percent"],
            "negotiated_price": result["discounted_price"], "pending_negotiation": {**offer,
             "original_price": result["original_price"], "discount_percent": result["applied_discount_percent"],
             "discounted_price": result["discounted_price"], "status": "accepted"}, "failure_reason": None}
