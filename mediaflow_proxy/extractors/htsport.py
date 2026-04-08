import re
import logging
from typing import Any, Dict

from bs4 import BeautifulSoup, SoupStrainer

from mediaflow_proxy.extractors.base import BaseExtractor, ExtractorError

logger = logging.getLogger(__name__)


class HTSportExtractor(BaseExtractor):
    """HTSport URL extractor for M3U8/MPD streams.

    Strategy:
    1. Fetch the main page URL.
    2. Parse HTML and extract the stream URL from the second <script> tag in <body>
       (XPath: /html/body/script[1]/text(), which is index 1 in 0-based).
    3. Detect M3U8 or MPD format and set the appropriate mediaflow endpoint.
    4. Return the stream URL with referer headers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mediaflow_endpoint = "hls_manifest_proxy"

    async def extract(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract stream URL from htsport.ws page."""
        try:
            logger.info(f"Fetching HTSport page: {url}")
            response = await self._make_request(
                url,
                headers={"Referer": "https://htsport.ws/"},
                timeout=15,
            )

            soup = BeautifulSoup(response.text, "lxml", parse_only=SoupStrainer("body"))
            body = soup.find("body")
            if not body:
                raise ExtractorError("Could not find <body> tag in the page")

            scripts = body.find_all("script")
            if len(scripts) < 2:
                raise ExtractorError(
                    f"Expected at least 2 <script> tags in <body>, found {len(scripts)}"
                )

            # XPath /html/body/script[1] is 1-indexed → index 1 in 0-based list
            script_content = scripts[1].get_text()
            if not script_content:
                raise ExtractorError("Second script tag in <body> is empty")

            logger.debug(f"Script content preview: {script_content[:300]}")

            # Extract the stream URL (M3U8 or MPD)
            stream_match = re.search(
                r'["\']?(https?://[^\s"\'<>]+\.(?:m3u8|mpd)[^\s"\'<>]*)["\']?',
                script_content,
            )
            if not stream_match:
                raise ExtractorError("Could not find M3U8 or MPD URL in script content")

            stream_url = stream_match.group(1)
            logger.info(f"Extracted stream URL: {stream_url}")

            # Choose endpoint based on format
            if stream_url.endswith(".mpd") or ".mpd?" in stream_url:
                mediaflow_endpoint = "proxy_stream_endpoint"
            else:
                mediaflow_endpoint = "hls_manifest_proxy"

            return {
                "destination_url": stream_url,
                "request_headers": {"Referer": url},
                "mediaflow_endpoint": mediaflow_endpoint,
            }

        except ExtractorError:
            raise
        except Exception as e:
            logger.exception(f"HTSport extraction failed for {url}")
            raise ExtractorError(f"Extraction failed: {str(e)}")
