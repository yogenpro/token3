"""Discover Vertex AI's public USD SKUs using Google's Cloud Billing Catalog API."""
import re

from .pricing_api import fetch_pages

SERVICES_URL = "https://cloudbilling.googleapis.com/v1/services?pageSize=500"


def vertex_catalog(api_key):
    # Header authentication keeps the key out of archived URLs and errors.
    headers = {"X-Goog-Api-Key": api_key}
    services, service_urls = fetch_pages(SERVICES_URL, "services", headers)
    candidates = [service for service in services["services"] if service.get("displayName") == "Vertex AI"]
    if len(candidates) != 1:
        raise ValueError("Cloud Billing catalog does not identify a unique Vertex AI service")
    service = candidates[0]
    name = service.get("name", "")
    if not re.fullmatch(r"services/[A-Za-z0-9_-]+", name):
        raise ValueError("Invalid Vertex AI billing service resource name")
    sku_url = "https://cloudbilling.googleapis.com/v1/{}/skus?currencyCode=USD&pageSize=500".format(name)
    skus, sku_urls = fetch_pages(sku_url, "skus", headers)
    names = [sku.get("name", "") for sku in skus["skus"]]
    if any(not sku.startswith(name + "/skus/") for sku in names) or len(set(names)) != len(names):
        raise ValueError("Unexpected or duplicate Vertex AI billing SKUs")
    # No model/modality filter: retain every public SKU, its regions, units,
    # effective pricingInfo/tieredRates and aggregation rules without coercion.
    payload = {"service": service, "service_discovery": services, "catalog": skus, "currency": "USD"}
    return payload, service_urls + sku_urls, sku_url
