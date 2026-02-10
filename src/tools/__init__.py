from .get_weather import get_weather
from .get_news import get_news
from .google_search import google_search
from .jina_reader import jina_reader


TOOLS = {
    "get_weather": get_weather,
    "get_news": get_news,
    "google_search": google_search,
    "jina_reader": jina_reader,
}
