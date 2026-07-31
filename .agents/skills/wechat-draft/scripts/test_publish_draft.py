import argparse
import unittest
from unittest.mock import patch

import publish_draft


class RaisingParser:
    def error(self, message):
        raise ValueError(message)


def make_args(**overrides):
    values = {
        "appid": "appid",
        "secret": "secret",
        "article_type": "news",
        "title": "标题",
        "content": "正文",
        "content_file": None,
        "author": "",
        "digest": "",
        "cover_image": None,
        "thumb_media_id": "thumb-id",
        "content_source_url": "",
        "image": [],
        "image_dir": None,
        "style_preset": "auto",
        "extra_css_file": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class ValidateArgsTests(unittest.TestCase):
    def setUp(self):
        self.parser = RaisingParser()

    def test_official_length_boundaries(self):
        publish_draft.validate_args(
            self.parser,
            make_args(title="题" * 32, author="作" * 16, digest="摘" * 120),
        )

        for field, value in (
            ("title", "题" * 33),
            ("author", "作" * 17),
            ("digest", "摘" * 121),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                publish_draft.validate_args(
                    self.parser,
                    make_args(**{field: value}),
                )

    def test_news_requires_cover(self):
        with self.assertRaisesRegex(ValueError, "cover-image"):
            publish_draft.validate_args(
                self.parser,
                make_args(thumb_media_id=None),
            )

    def test_newspic_uses_same_title_limit(self):
        publish_draft.validate_args(
            self.parser,
            make_args(
                article_type="newspic",
                title="题" * 32,
                content=None,
                thumb_media_id=None,
                image=["card.png"],
            ),
        )
        with self.assertRaises(ValueError):
            publish_draft.validate_args(
                self.parser,
                make_args(
                    article_type="newspic",
                    title="题" * 33,
                    content=None,
                    thumb_media_id=None,
                    image=["card.png"],
                ),
            )


class ArticlePayloadTests(unittest.TestCase):
    @patch("publish_draft.prepare_content", return_value="<p>正文</p>")
    def test_news_payload(self, _prepare_content):
        article = publish_draft.build_news_article(make_args(), "token")

        self.assertEqual(article["article_type"], "news")
        self.assertEqual(article["thumb_media_id"], "thumb-id")
        self.assertNotIn("is_original", article)
        self.assertNotIn("advertisement", article)

    @patch("publish_draft.upload_cover_image", return_value=None)
    def test_news_stops_when_cover_upload_fails(self, _upload_cover):
        with self.assertRaisesRegex(RuntimeError, "封面图片上传失败"):
            publish_draft.build_news_article(
                make_args(cover_image="cover.png", thumb_media_id=None),
                "token",
            )

    @patch("publish_draft.prepare_newspic_content", return_value="正文")
    @patch("publish_draft.upload_newspic_image", return_value="image-id")
    @patch("publish_draft.collect_newspic_image_paths", return_value=["card.png"])
    @patch("publish_draft.os.path.exists", return_value=True)
    def test_newspic_payload(self, _exists, _collect, _upload, _prepare):
        article = publish_draft.build_newspic_article(
            make_args(
                article_type="newspic",
                content=None,
                thumb_media_id=None,
                image=["card.png"],
            ),
            "token",
        )

        self.assertEqual(article["article_type"], "newspic")
        self.assertEqual(
            article["image_info"]["image_list"],
            [{"image_media_id": "image-id"}],
        )
        self.assertNotIn("is_original", article)
        self.assertNotIn("advertisement", article)


if __name__ == "__main__":
    unittest.main()
