import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).with_name("azure_generate_image.py")
SPEC = importlib.util.spec_from_file_location("azure_generate_image", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AzureGenerateImageTests(unittest.TestCase):
    def test_flare_endpoint_auth_and_png_compression(self):
        endpoint = (
            "https://example.test/openai/deployments/gpt-image-2.5-flare/"
            "images/generations?api-version=preview"
        )

        self.assertEqual(MODULE.DEFAULT_DEPLOYMENT, "gpt-image-2.5-flare")
        self.assertEqual(
            MODULE._build_operation_url(endpoint, "ignored", "ignored", "edits"),
            endpoint.replace("/generations", "/edits"),
        )
        self.assertEqual(
            MODULE._build_headers("secret", auth_style="bearer"),
            {"Authorization": "Bearer secret"},
        )

        payload = MODULE._build_generation_payload(
            "A red fox",
            size="1024x1024",
            quality="low",
            output_format="png",
            output_compression=100,
            n=1,
            background="auto",
        )
        self.assertEqual(payload["output_compression"], 100)

    def test_legacy_endpoint_uses_matching_legacy_key(self):
        values = {
            "AZURE_API_KEY": "unrelated-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "openai-key",
        }

        with patch.object(MODULE, "_resolve_env", side_effect=values.get):
            endpoint, api_key, auth_style = MODULE._resolve_credentials(None, None)

        self.assertEqual(endpoint, values["AZURE_OPENAI_ENDPOINT"])
        self.assertEqual(api_key, values["AZURE_OPENAI_API_KEY"])
        self.assertEqual(auth_style, "api-key")

    def test_resource_root_uses_v1_generation_endpoint(self):
        self.assertEqual(
            MODULE._build_operation_url(
                "https://example.openai.azure.com",
                "gpt-image-2.5-flare",
                "preview",
                "generations",
            ),
            "https://example.openai.azure.com/openai/v1/images/"
            "generations?api-version=preview",
        )


if __name__ == "__main__":
    unittest.main()
