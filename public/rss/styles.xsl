<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:atom="http://www.w3.org/2005/Atom">
  <xsl:output method="html" version="1.0" encoding="UTF-8" indent="yes"/>
  <xsl:template match="/">
    <html xmlns="http://www.w3.org/1999/xhtml">
      <head>
        <title><xsl:value-of select="/rss/channel/title"/> - RSS Feed</title>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1"/>
        <style type="text/css">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
            background: #f9f9f9;
          }
          a {
            color: #0366d6;
            text-decoration: none;
          }
          a:hover {
            text-decoration: underline;
          }
          header {
            display: flex;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #eee;
          }
          header img {
            width: 60px;
            height: 60px;
            margin-right: 1rem;
            border-radius: 50%;
          }
          h1 {
            font-size: 1.8rem;
            margin: 0;
            font-weight: 600;
          }
          h2 {
            font-size: 1.2rem;
            margin: 0 0 0.5rem 0;
            font-weight: 500;
          }
          .description {
            margin: 0.5rem 0 0 0;
            color: #666;
          }
          .item {
            margin-bottom: 2.5rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid #eee;
          }
          .item:last-child {
            border-bottom: none;
          }
          .pubDate {
            color: #666;
            font-size: 0.85rem;
            margin-bottom: 1rem;
          }
          .category {
            display: inline-block;
            background: #f0f0f0;
            padding: 0.2rem 0.5rem;
            border-radius: 3px;
            font-size: 0.75rem;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
            color: #444;
          }
          footer {
            margin-top: 3rem;
            text-align: center;
            color: #666;
            font-size: 0.85rem;
          }
        </style>
      </head>
      <body>
        <header>
          <xsl:if test="/rss/channel/image">
            <img>
              <xsl:attribute name="src">
                <xsl:value-of select="/rss/channel/image/url"/>
              </xsl:attribute>
              <xsl:attribute name="alt">
                <xsl:value-of select="/rss/channel/title"/>
              </xsl:attribute>
            </img>
          </xsl:if>
          <div>
            <h1>
              <xsl:value-of select="/rss/channel/title"/>
            </h1>
            <p class="description">
              <xsl:value-of select="/rss/channel/description"/>
            </p>
            <p>
              <a>
                <xsl:attribute name="href">
                  <xsl:value-of select="/rss/channel/link"/>
                </xsl:attribute>
                访问网站
              </a>
            </p>
          </div>
        </header>
        
        <main>
          <xsl:for-each select="/rss/channel/item">
            <article class="item">
              <h2>
                <a>
                  <xsl:attribute name="href">
                    <xsl:value-of select="link"/>
                  </xsl:attribute>
                  <xsl:value-of select="title"/>
                </a>
              </h2>
              
              <p class="pubDate">
                发布于: <xsl:value-of select="pubDate"/>
                <xsl:if test="author">
                  - 作者: <xsl:value-of select="author"/>
                </xsl:if>
              </p>
              
              <xsl:if test="category">
                <div>
                  <xsl:for-each select="category">
                    <span class="category">
                      <xsl:value-of select="."/>
                    </span>
                  </xsl:for-each>
                </div>
              </xsl:if>
              
              <div>
                <xsl:value-of select="description" disable-output-escaping="yes"/>
              </div>
              
              <p>
                <a>
                  <xsl:attribute name="href">
                    <xsl:value-of select="link"/>
                  </xsl:attribute>
                  阅读全文 →
                </a>
              </p>
            </article>
          </xsl:for-each>
        </main>
        
        <footer>
          <p>
            <xsl:value-of select="/rss/channel/copyright"/>
            <br/>
            最后更新于: <xsl:value-of select="/rss/channel/lastBuildDate"/>
          </p>
          <p>
            <a>
              <xsl:attribute name="href">
                <xsl:value-of select="/rss/channel/atom:link/@href"/>
              </xsl:attribute>
              RSS Feed
            </a> - 使用RSS阅读器订阅此内容
          </p>
        </footer>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>