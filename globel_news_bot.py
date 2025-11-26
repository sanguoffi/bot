import requests
import time
import logging
import re
import html
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pickle
import os

# Setup logging for Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== CONFIGURATION =====
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8479210213:AAHi5qqaaGkZ8Jyb9ANwWjjcUqbqbxHGbtY")
CHAT_ID = os.environ.get('CHAT_ID', "@GlobelNewsAlert")

# News Sources (Updated with more reliable feeds)
RSS_FEEDS = [
    {'name': 'Reuters World', 'url': 'https://www.reutersagency.com/feed/?best-regions=world&post-type=best'},
    {'name': 'AP Top News', 'url': 'https://rss.ap.org/rss/topnews'},
    {'name': 'NPR World', 'url': 'https://feeds.npr.org/1004/rss.xml'},
    {'name': 'CBC World', 'url': 'https://rss.cbc.ca/lineup/world.xml'},
    {'name': 'France 24', 'url': 'https://www.france24.com/en/rss'},
]
# Bot Settings
POST_INTERVAL = int(os.environ.get('POST_INTERVAL', '900'))
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '3'))
DELAY_BETWEEN_POSTS = int(os.environ.get('DELAY_BETWEEN_POSTS', '2'))
MAX_NEWS_AGE_HOURS = int(os.environ.get('MAX_NEWS_AGE_HOURS', '8'))

# ===== TELEGRAM SENDER =====
class TelegramSender:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, text, parse_mode="HTML"):
        """Send message to Telegram channel"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get('ok'):
                logger.info("✅ Message sent successfully")
                return True
            else:
                logger.error(f"❌ Telegram API error: {result.get('description')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to send message: {e}")
            return False
    
    def send_photo(self, photo_url, caption):
        """Send photo with caption to Telegram channel"""
        url = f"{self.base_url}/sendPhoto"
        payload = {
            'chat_id': self.chat_id,
            'photo': photo_url,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get('ok'):
                logger.info("✅ Photo sent successfully")
                return True
            else:
                logger.error(f"❌ Telegram photo error: {result.get('description')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to send photo: {e}")
            return False
    
    def test_connection(self):
        """Test bot connection"""
        url = f"{self.base_url}/getMe"
        
        try:
            response = requests.get(url, timeout=10)
            result = response.json()
            
            if result.get('ok'):
                bot_info = result['result']
                logger.info(f"✅ Bot connected: {bot_info['username']}")
                return True
            else:
                logger.error(f"❌ Bot connection failed: {result.get('description')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False

# ===== IMPROVED RSS PARSER =====
class SimpleRSSParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def parse_rss_feed(self, feed_url, source_name):
        """Parse RSS feed with retry logic"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                logger.info(f"📡 Fetching from {source_name} (attempt {attempt + 1})")
                response = self.session.get(feed_url, timeout=15)
                response.raise_for_status()
                
                # Try different parsers
                try:
                    soup = BeautifulSoup(response.content, 'lxml-xml')
                except:
                    try:
                        soup = BeautifulSoup(response.content, 'xml')
                    except:
                        soup = BeautifulSoup(response.content, 'html.parser')
                
                items = soup.find_all('item') or soup.find_all('entry')
                
                news_items = []
                for item in items[:10]:  # Get latest 10 items
                    news_item = self._parse_rss_item(item, source_name)
                    if news_item and self._is_valid_news(news_item):
                        news_items.append(news_item)
                
                if news_items:
                    logger.info(f"✅ Found {len(news_items)} from {source_name}")
                return news_items
                
            except Exception as e:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed for {source_name}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
                    continue
                else:
                    logger.error(f"❌ All attempts failed for {source_name}")
                    return []
    
    def _parse_rss_item(self, item, source_name):
        """Parse individual RSS item"""
        try:
            # Extract title
            title_elem = item.find('title')
            if not title_elem:
                return None
            title = title_elem.get_text().strip()
            
            # Extract description
            description_elem = item.find('description') or item.find('summary') or item.find('content')
            description = description_elem.get_text().strip() if description_elem else ""
            
            # Extract link
            link_elem = item.find('link')
            if not link_elem:
                return None
            link = link_elem.get('href') or link_elem.get_text().strip()
            
            # Extract publication date
            pub_date = self._parse_pub_date(item)
            
            # Extract image
            image_url = self._extract_image(item)
            
            # Clean description
            description = self._clean_html(description)
            if len(description) > 300:
                description = description[:297] + "..."
            
            return {
                'title': title,
                'description': description,
                'url': link,
                'image_url': image_url,
                'source': source_name,
                'published_at': pub_date
            }
            
        except Exception as e:
            logger.debug(f"Debug parsing RSS item: {e}")
            return None
    
    def _parse_pub_date(self, item):
        """Parse publication date from various possible fields"""
        date_fields = ['pubdate', 'pubDate', 'date', 'published', 'updated', 'dc:date']
        
        for field in date_fields:
            date_elem = item.find(field)
            if date_elem and date_elem.get_text():
                try:
                    date_str = date_elem.get_text().strip()
                    # Try to parse various date formats
                    for fmt in ['%a, %d %b %Y %H:%M:%S %Z', 
                               '%a, %d %b %Y %H:%M:%S %z',
                               '%Y-%m-%dT%H:%M:%SZ',
                               '%Y-%m-%d %H:%M:%S',
                               '%d %b %Y %H:%M:%S %Z']:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            return parsed_date.replace(tzinfo=None)
                        except ValueError:
                            continue
                except:
                    continue
        
        return datetime.now()
    
    def _extract_image(self, item):
        """Extract image URL from RSS item"""
        try:
            # Check for media:content
            media_content = item.find('media:content') or item.find('media:thumbnail')
            if media_content:
                return media_content.get('url', '')
            
            # Check for enclosure
            enclosure = item.find('enclosure')
            if enclosure and enclosure.get('type', '').startswith('image'):
                return enclosure.get('url', '')
            
            # Check description for images
            description = item.find('description') or item.find('summary') or item.find('content')
            if description:
                desc_text = description.get_text()
                images = re.findall(r'src="([^"]+\.(?:jpg|jpeg|png|webp))"', desc_text)
                if images:
                    return images[0]
                    
        except Exception:
            pass
        
        return ""
    
    def _clean_html(self, text):
        """Remove HTML tags from text"""
        if not text:
            return ""
        return re.sub(r'<[^>]+>', '', text)
    
    def _is_valid_news(self, news_item):
        """Validate news item"""
        if not news_item:
            return False
            
        # Check if news is within 8 hours
        if news_item['published_at']:
            time_diff = datetime.now() - news_item['published_at']
            if time_diff.total_seconds() > (MAX_NEWS_AGE_HOURS * 3600):
                return False
        
        return (len(news_item['title']) > 10 and 
                len(news_item['description']) > 20 and
                news_item['url'].startswith('http'))

# ===== NEWS FETCHER =====
class SimpleNewsFetcher:
    def __init__(self):
        self.parser = SimpleRSSParser()
    
    def fetch_news(self):
        """Fetch news from all RSS feeds"""
        all_news = []
        
        for feed_config in RSS_FEEDS:
            try:
                news_items = self.parser.parse_rss_feed(feed_config['url'], feed_config['name'])
                if news_items:
                    all_news.extend(news_items)
                time.sleep(3)  # Longer delay between requests
            except Exception as e:
                logger.error(f"❌ Error with {feed_config['name']}: {e}")
                continue
        
        return self._deduplicate_news(all_news)
    
    def _deduplicate_news(self, news_list):
        """Remove duplicate news"""
        seen_titles = set()
        unique_news = []
        
        for news in news_list:
            if not news:
                continue
                
            title_key = news['title'][:50].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_news.append(news)
        
        unique_news.sort(key=lambda x: x['published_at'] if x['published_at'] else datetime.now(), reverse=True)
        return unique_news[:10]

# ===== NEWS FORMATTER =====
def format_news(news_item):
    """Format news for Telegram"""
    title = html.escape(news_item['title'])
    description = html.escape(news_item['description'])
    source = html.escape(news_item['source'])
    
    time_ago = get_time_ago(news_item['published_at'])
    
    message = f"""<b>📰 {title}</b>

📝 {description}

🏢 Source: {source}
⏰ {time_ago}

🔗 <a href="{news_item['url']}">Read Full Story</a>

#GlobalNews #BreakingNews #{source.replace(' ', '')}"""
    
    return message, news_item['image_url']

def get_time_ago(published_at):
    """Get human-readable time difference"""
    if not published_at:
        return "Recently"
        
    diff = datetime.now() - published_at
    hours = int(diff.total_seconds() // 3600)
    minutes = int((diff.total_seconds() % 3600) // 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m ago"
    elif minutes > 0:
        return f"{minutes}m ago"
    else:
        return "Just now"

# ===== PERSISTENT STORAGE =====
class NewsStorage:
    def __init__(self, storage_file='posted_news.pkl'):
        self.storage_file = storage_file
        self.posted_urls = self._load_posted_urls()
    
    def _load_posted_urls(self):
        """Load posted URLs from file"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'rb') as f:
                    return set(pickle.load(f))
        except Exception as e:
            logger.error(f"Error loading storage: {e}")
        return set()
    
    def save_posted_urls(self):
        """Save posted URLs to file"""
        try:
            with open(self.storage_file, 'wb') as f:
                pickle.dump(list(self.posted_urls), f)
        except Exception as e:
            logger.error(f"Error saving storage: {e}")
    
    def add_posted_url(self, url):
        """Add URL to posted list"""
        self.posted_urls.add(url)
        self.save_posted_urls()
    
    def is_url_posted(self, url):
        """Check if URL was already posted"""
        return url in self.posted_urls
    
    def cleanup_old_urls(self, max_urls=100):
        """Keep only recent URLs"""
        if len(self.posted_urls) > max_urls:
            urls_list = list(self.posted_urls)
            self.posted_urls = set(urls_list[-max_urls:])
            self.save_posted_urls()

# ===== MAIN BOT =====
class SimpleNewsBot:
    def __init__(self):
        self.sender = TelegramSender(BOT_TOKEN, CHAT_ID)
        self.fetcher = SimpleNewsFetcher()
        self.storage = NewsStorage()
    
    def run_cycle(self):
        """Run one news posting cycle"""
        try:
            logger.info("🔄 Fetching latest news...")
            news_list = self.fetcher.fetch_news()
            
            if not news_list:
                logger.warning("❌ No fresh news found in this cycle")
                # Send a status message occasionally
                if int(time.time()) % 3600 < 60:  # Once per hour
                    self.sender.send_message("🤖 <b>Global News Bot Status</b>\n\n✅ Bot is running and monitoring news sources\n⏰ Next check in 15 minutes\n🌍 Sources: BBC, CNN, Al Jazeera, Guardian, DW")
                return
            
            logger.info(f"📰 Found {len(news_list)} fresh news items")
            
            posted_count = 0
            for news in news_list[:BATCH_SIZE]:
                if self.storage.is_url_posted(news['url']):
                    logger.info(f"⏭️ Skipping duplicate: {news['title'][:50]}...")
                    continue
                
                caption, image_url = format_news(news)
                
                success = False
                if image_url and image_url.startswith('http'):
                    success = self.sender.send_photo(image_url, caption)
                
                if not success:
                    success = self.sender.send_message(caption)
                
                if success:
                    posted_count += 1
                    self.storage.add_posted_url(news['url'])
                    logger.info(f"✅ Posted: {news['title'][:50]}...")
                    
                    if posted_count < BATCH_SIZE:
                        time.sleep(DELAY_BETWEEN_POSTS)
            
            logger.info(f"🎉 Cycle completed: Posted {posted_count} news items")
            self.storage.cleanup_old_urls()
                
        except Exception as e:
            logger.error(f"❌ Cycle error: {e}")

def main():
    """Main function"""
    logger.info("🚀 Starting Global News Bot on Render...")
    
    bot = SimpleNewsBot()
    
    logger.info("🔗 Testing bot connection...")
    if not bot.sender.test_connection():
        logger.error("❌ Cannot start bot due to connection issues")
        return
    
    logger.info("🌍 Global News Bot Started!")
    logger.info(f"⏰ Posting every {POST_INTERVAL//60} minutes")
    logger.info(f"📦 Batch size: {BATCH_SIZE} posts per cycle")
    logger.info(f"📡 Monitoring {len(RSS_FEEDS)} news sources")
    
    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            logger.info(f"🔄 Starting cycle #{cycle_count}")
            
            bot.run_cycle()
            
            logger.info(f"⏳ Waiting {POST_INTERVAL//60} minutes for next cycle...")
            time.sleep(POST_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        logger.info("🔄 Restarting in 60 seconds...")
        time.sleep(60)
        main()

if __name__ == "__main__":
    main()

