"""Thumbnail metadata: owner avatars and custom GitHub social previews."""

import io
import json
import unittest

from dsh_forge.previews import (
    GITHUB_GRAPHQL,
    PreviewError,
    apply_social_previews,
    fetch_social_previews,
    repository_slugs,
    safe_avatar_url,
    safe_preview_url,
)
from dsh_forge.registry import _fork


PREVIEW = "https://repository-images.githubusercontent.com/1333146268/3f2a9c1e-1b2c-4d5e-8f90-a1b2c3d4e5f6"


class FakeResponse(io.BytesIO):
    def __init__(self, payload, url=GITHUB_GRAPHQL):
        super().__init__(json.dumps(payload).encode())
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class PreviewTests(unittest.TestCase):
    def test_only_github_hosted_images_are_accepted(self):
        self.assertEqual(safe_preview_url(PREVIEW), PREVIEW)
        for value in (
            "https://opengraph.githubassets.com/1/octo/repo",
            "http://repository-images.githubusercontent.com/1/abcdefgh",
            PREVIEW + "?x=1",
            "javascript:alert(1)",
            None,
        ):
            self.assertIsNone(safe_preview_url(value))
        self.assertEqual(safe_avatar_url("https://avatars.githubusercontent.com/u/42?v=4"), "https://avatars.githubusercontent.com/u/42?v=4")
        self.assertIsNone(safe_avatar_url("https://evil.example/u/42"))

    def test_batches_record_custom_previews_only(self):
        queries = []

        def opener(request, timeout):
            body = json.loads(request.data)
            queries.append(body["query"])
            self.assertEqual(request.get_header("Authorization"), "Bearer token")
            data = {}
            for index, line in enumerate(body["query"].splitlines()[1:-1]):
                name = line.split('name: "', 1)[1].split('"', 1)[0]
                data[f"r{index}"] = (
                    {"usesCustomOpenGraphImage": True, "openGraphImageUrl": PREVIEW} if name == "custom"
                    else ({"usesCustomOpenGraphImage": False, "openGraphImageUrl": "https://opengraph.githubassets.com/x"} if name == "generated" else None)
                )
            return FakeResponse({"data": data})

        previews, coverage = fetch_social_previews(
            ["octo/custom", "octo/generated", "octo/missing", 'bad/"injected'], token="token", opener=opener, batch_size=2,
        )
        self.assertEqual(previews, {"octo/custom": PREVIEW})
        self.assertEqual(len(queries), 2)
        self.assertNotIn("injected", "".join(queries))
        self.assertEqual(coverage["status"], "complete")
        self.assertEqual(coverage["checked_count"], 3)

    def test_a_failed_batch_marks_coverage_incomplete(self):
        def opener(request, timeout):
            return FakeResponse({"data": {"r0": None}}, url="https://evil.example/graphql")

        previews, coverage = fetch_social_previews(["octo/a"], token="token", opener=opener)
        self.assertEqual(previews, {})
        self.assertEqual(coverage["status"], "incomplete")
        self.assertIn("redirected", coverage["failure"])

    def test_token_is_required(self):
        with self.assertRaises(PreviewError):
            fetch_social_previews(["octo/a"], token="")

    def test_apply_sets_and_clears_fields(self):
        snapshot = {
            "entries": [{"full_name": "octo/custom"}, {"full_name": "octo/plain", "social_preview_url": PREVIEW}],
            "supplemental_entries": [{"full_name": "octo/plugin"}],
        }
        self.assertEqual(repository_slugs(snapshot), ["octo/custom", "octo/plain", "octo/plugin"])
        self.assertEqual(apply_social_previews(snapshot, {"octo/custom": PREVIEW, "octo/plugin": "https://evil.example/x"}), 1)
        self.assertEqual(snapshot["entries"][0]["social_preview_url"], PREVIEW)
        self.assertNotIn("social_preview_url", snapshot["entries"][1])
        self.assertNotIn("social_preview_url", snapshot["supplemental_entries"][0])

    def test_fork_indexing_keeps_a_safe_owner_avatar(self):
        repo = {
            "id": 7, "node_id": "R_x", "full_name": "octo/fork", "fork": True, "private": False,
            "owner": {"login": "octo", "avatar_url": "https://avatars.githubusercontent.com/u/9?v=4"},
            "stargazers_count": 1, "forks_count": 0, "topics": [],
        }
        self.assertEqual(_fork(repo, "deepseek-ai/deepseek-harness")["owner_avatar_url"], "https://avatars.githubusercontent.com/u/9?v=4")
        repo["owner"]["avatar_url"] = "https://tracker.example/pixel.gif"
        self.assertNotIn("owner_avatar_url", _fork(repo, "deepseek-ai/deepseek-harness"))


if __name__ == "__main__":
    unittest.main()
