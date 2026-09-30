import feedparser
import urllib.parse
import urllib.request
import time
from typing import Dict


class DynamicNewsIngestor:
    """
    Supplychainer Stage 1: Dynamic News Ingestion.

    Uses Google News RSS with:
    - location-aware queries
    - local caching
    - bounded network timeout
    - deterministic fallback
    """

    def __init__(self):

        self.cache: Dict[str, tuple] = {}

        # Mission Control:
        # 15-minute cache prevents repeated external
        # telemetry requests during route evaluation.
        self.cache_ttl = 900

        self.fallback_news = {

            "sea":
                "Maritime congestion reported at major "
                "transshipment hubs. Berthing delays expected.",

            "air":
                "Aviation fuel surcharge volatility and cargo "
                "handling backlogs noted in international airports.",

            "road":
                "Highway traffic density increasing in primary "
                "logistics corridors.",

            "rail":
                "Rail freight scheduling adjustments due to "
                "infrastructure maintenance."
        }

    def get_latest_news(
        self,
        location: str,
        transport_mode: str
    ) -> str:

        mode = (
            transport_mode or ""
        ).lower().strip()

        location = (
            location or ""
        ).strip()

        query = (
            f"{location} {mode} "
            f"logistics disruption"
        )

        now = time.time()

        # Mission Control:
        # Reuse recent orbital telemetry.
        cached = self.cache.get(query)

        if cached:

            timestamp, content = cached

            if (
                now - timestamp
                < self.cache_ttl
            ):
                return content

        t_start = time.perf_counter()

        print(
            f"[TRACE] STEP 7: News ingestion started "
            f"for {location}"
        )

        try:

            encoded_query = (
                urllib.parse.quote(query)
            )

            rss_url = (
                "https://news.google.com/rss/search?"
                f"q={encoded_query}"
                "&hl=en-US"
                "&gl=US"
                "&ceid=US:en"
            )

            # Mission Control:
            # Apply timeout only to this RSS request instead
            # of modifying Python's global socket configuration.
            with urllib.request.urlopen(
                rss_url,
                timeout=2.0
            ) as response:

                feed = feedparser.parse(
                    response
                )

            print(
                f"[NEWS DEBUG] Entries: "
                f"{len(feed.entries)}"
            )

            print(
                f"[NEWS DEBUG] Status: "
                f"{getattr(feed, 'status', 'NO STATUS')}"
            )

            if feed.entries:

                headlines = []

                for entry in feed.entries[:3]:

                    title = getattr(
                        entry,
                        "title",
                        ""
                    ).strip()

                    if title:
                        headlines.append(
                            title
                        )

                if headlines:

                    content = " | ".join(
                        headlines
                    )

                    self.cache[query] = (
                        now,
                        content
                    )

                    print(
                        "[TRACE] STEP 8: News ingestion "
                        f"complete "
                        f"({time.perf_counter() - t_start:.4f}s)"
                    )

                    return content

        except Exception as e:

            print(
                f"[TRACE] News ingestion error "
                f"for {query}: {e}"
            )

        print(
            "[TRACE] STEP 8: News ingestion complete "
            "(Fallback used)"
        )

        return self.fallback_news.get(
            mode,
            "Normal operational conditions reported."
        )