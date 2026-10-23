import argparse
import re
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

import publish_draft
from style_manager import build_styled_fragment


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
        "delete_draft": None,
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


class CodeBlockFormattingTests(unittest.TestCase):
    @staticmethod
    def visible_code(fragment):
        """模拟 white-space 被微信重置后的文本，只认 br 换行。"""
        soup = BeautifulSoup(fragment, "html.parser")
        block = soup.find("pre")
        for br in block.find_all("br"):
            br.replace_with("\u2028")
        text = re.sub(r"[ \t\r\n]+", " ", block.get_text())
        return text.replace("\u2028", "\n").replace("\xa0", " ")

    def test_publishing_preserves_reported_three_commands_without_whitespace_css(self):
        commands = (
            "winget install Microsoft.WinAppCli\n"
            "dotnet --version   # 应为 10.x\n"
            "winapp --version   # 应为 0.7.x 或更高"
        )
        args = make_args(
            content=f"```bash\n{commands}\n```",
            content_format="markdown",
            ignore_image_errors=False,
        )
        output = publish_draft.prepare_content(args, "unused-token")
        self.assertEqual(self.visible_code(output).rstrip("\n"), commands)

    def test_both_markdown_converters_and_all_presets_preserve_blank_lines_and_indent(self):
        code = 'if (x < 2 && ready) {\n    Print("中文 & <tag>");\n\n    return;\n}'
        for converter in (
            publish_draft.markdown_to_html,
            publish_draft.basic_markdown_to_html,
        ):
            for preset in ("default", "code", "essay", "guide", "none"):
                with self.subTest(converter=converter.__name__, preset=preset):
                    output = build_styled_fragment(
                        converter(f"```csharp\n{code}\n```"), preset, ""
                    )
                    self.assertEqual(self.visible_code(output).rstrip("\n"), code)
                    self.assertIsNone(BeautifulSoup(output, "html.parser").find("tag"))

    def test_html_highlighting_existing_breaks_tabs_and_inline_code(self):
        fragment = (
            '<p><code>inline code</code></p><pre><code class="language-python">'
            '<span style="color: red">if</span> x:\r\n'
            '\tprint(&quot;&lt;ok&gt;&quot;)<br>\n'
            '\treturn x</code></pre>'
        )
        # A newline after an existing br is also a real source newline.
        expected = 'if x:\n    print("<ok>")\n\n    return x'
        output = build_styled_fragment(fragment, "code", "")
        self.assertEqual(self.visible_code(output), expected)
        soup = BeautifulSoup(output, "html.parser")
        self.assertEqual(soup.select_one("p code").get_text(), "inline code")
        self.assertEqual(soup.select_one("pre span").get_text(), "if")
        self.assertIn("color: red", soup.select_one("pre span")["style"])
        second_output = build_styled_fragment(output, "code", "")
        self.assertEqual(self.visible_code(second_output), expected)

    def test_html_pre_without_code_tag(self):
        output = build_styled_fragment("<pre>one\n  two\n\nthree</pre>", "none", "")
        self.assertEqual(self.visible_code(output), "one\n  two\n\nthree")


if __name__ == "__main__":
    unittest.main()
