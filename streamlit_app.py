import streamlit as st
import feedparser
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator # 정확한 임포트 경로
import datetime
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="셜록 아티클 피드 (동적 생성)",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Constants for RSS Generation ---
RSS_ARCHIVES_URL = "https://www.neosherlock.com/archives"
# 생성될 RSS 파일 이름이자, Streamlit 앱이 읽을 파일 이름
RSS_FILE_PATH = "neosherlock_feed_final.xml"
RSS_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# --- RSS Generation Functions ---
def fetch_html_for_rss(url):
    headers = {'User-Agent': RSS_USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=15) # 타임아웃 약간 늘림
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"🚫 RSS Gen: URL 접근 중 오류 발생: {url} - {e}") # 서버 로그용
        return None

def parse_articles_for_rss(html_content):
    """HTML 내용을 파싱하여 기사 정보를 추출합니다. (사용자 제공 HTML 기반으로 검증된 로직)"""
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, 'html.parser')
    articles_data = []
    main_content = soup.find('main', id='main')
    if not main_content:
        print("🚨 RSS Gen: <main id='main'> 요소를 찾지 못했습니다.")
        return []

    article_list_ul = main_content.find('ul', class_='list list-thumbnail-horizontal')
    if not article_list_ul:
        article_list_ul = main_content.find('ul', class_=lambda c: c and 'list' in c and 'list-thumbnail-horizontal' in c)
        if not article_list_ul:
             print("🚫 RSS Gen: <main id='main'> 내에서 기사 목록 ul 태그를 찾을 수 없습니다.")
             return []

    list_items = article_list_ul.find_all('li', class_='list-item', recursive=False)
    if not list_items:
        print("🚫 RSS Gen: 기사 목록 ul 태그 내에서 <li class='list-item'>을 찾을 수 없습니다.")
        return []
    
    korea_tz = datetime.timezone(datetime.timedelta(hours=9)) # KST (UTC+9)

    for item_li in list_items:
        anchor_tag = item_li.find('a', class_='item-inner')
        if not anchor_tag: continue

        article_url = anchor_tag.get('href')
        if not article_url: continue
            
        text_div = anchor_tag.find('div', class_='item-text')
        if not text_div: continue

        title = "제목 없음"
        summary = "요약 없음"
        author_name = "작성자 미상"
        published_time_obj = datetime.datetime.now(datetime.timezone.utc) # 기본값

        title_div = text_div.find('div', class_='item-title')
        if title_div:
            title = title_div.text.strip()

        excerpt_div = text_div.find('div', class_='item-excerpt')
        if excerpt_div:
            if excerpt_div.p:
                summary = " ".join(excerpt_div.p.text.split())
            else:
                summary = " ".join(excerpt_div.text.split())
        
        subinfo_tags = text_div.find_all('div', class_='item-subinfo')
        
        if len(subinfo_tags) > 0:
            author_candidate = subinfo_tags[0].text.strip()
            if author_candidate:
                author_name = author_candidate

        if len(subinfo_tags) > 1:
            date_str_candidate = subinfo_tags[1].text.strip()
            if date_str_candidate:
                try:
                    dt_naive = datetime.datetime.strptime(date_str_candidate, "%Y.%m.%d")
                    published_time_obj = dt_naive.replace(tzinfo=korea_tz)
                except ValueError:
                    print(f"⚠️ RSS Gen: 날짜 형식 변환 오류 (기사: '{title[:30]}...'): '{date_str_candidate}'.")
        
        articles_data.append({
            'title': title,
            'author': author_name,
            'summary': summary,
            'url': article_url,
            'published_time': published_time_obj
        })
    return articles_data

def create_feed_xml_for_rss(articles_data, site_url):
    fg = FeedGenerator()
    fg.title('Neosherlock Archives RSS Feed (동적 생성)')
    fg.link(href=site_url, rel='alternate')
    fg.description('neosherlock.com 아카이브의 기사 정보 RSS 피드 (Streamlit 앱에서 동적 생성)')
    fg.language('ko')
    
    for article_info in articles_data:
        fe = fg.add_entry()
        fe.id(article_info['url']) 
        fe.title(article_info['title'])
        fe.link(href=article_info['url'], rel='alternate')
        fe.description(article_info['summary'])
        fe.author({'name': article_info['author']})
        fe.pubDate(article_info['published_time'])
    
    return fg.rss_str(pretty=True)

def save_rss_to_file(rss_xml_bytes, filepath):
    try:
        with open(filepath, 'wb') as f:
            f.write(rss_xml_bytes)
        return True
    except IOError as e:
        print(f"🚫 RSS Gen: 파일 저장 중 오류 발생: {filepath} - {e}")
        return False

@st.cache_data(ttl=3600) # 1시간 (3600초) 동안 결과 캐시
def generate_and_save_rss_feed_cached(output_filepath):
    """
    RSS 피드를 생성하고 파일로 저장하는 전체 과정을 수행합니다.
    성공 시 True, 실패 시 False를 반환합니다. Streamlit UI 직접 호출은 피합니다.
    """
    print(f"[{datetime.datetime.now()}] RSS 피드 생성 시도: {output_filepath}") # 서버 로그
    
    html_content = fetch_html_for_rss(RSS_ARCHIVES_URL)
    if not html_content:
        print("RSS Gen: HTML 가져오기 실패.")
        return False

    articles = parse_articles_for_rss(html_content)
    # 기사가 없어도 빈 피드를 생성할 수 있으므로, articles가 비었다고 바로 False를 반환하지는 않습니다.
    # print(f"RSS Gen: 파싱된 기사 수: {len(articles)}")

    rss_xml_bytes = create_feed_xml_for_rss(articles, RSS_ARCHIVES_URL)
    
    if save_rss_to_file(rss_xml_bytes, output_filepath):
        print(f"RSS Gen: '{output_filepath}' 파일 저장 성공.")
        return True
    else:
        print(f"RSS Gen: '{output_filepath}' 파일 저장 실패.")
        return False

# --- RSS Feed Display Functions (이전과 유사) ---
def load_feed_for_display(file_path):
    """표시를 위해 로컬 RSS 파일을 로드하고 파싱합니다."""
    if not os.path.exists(file_path):
        # 이 함수는 RSS 생성 후 호출되므로, 파일이 없다면 생성 실패를 의미할 수 있음
        # st.error는 호출하는 쪽에서 처리하도록 메시지 반환 안함
        return None
    try:
        feed = feedparser.parse(file_path)
        if feed.bozo:
            # UI에 직접 경고하기보다 호출한 쪽에서 처리
            print(f"⚠️ RSS Display: 피드 파싱 중 문제 발생 가능성: {feed.bozo_exception}")
        return feed
    except Exception as e:
        print(f"🚨 RSS Display: 파일 읽기/파싱 중 예외: {e}")
        return None

# --- Main Application UI ---
st.title("📰 셜록 아티클 피드 (자동 업데이트)")
st.caption(f"'{RSS_FILE_PATH}' 파일을 사용하며, 주기적으로 최신 기사를 가져옵니다.")
st.markdown("---")

# RSS 피드 생성 또는 업데이트 시도 (캐시된 함수 호출)
with st.spinner("최신 기사 정보를 확인하고 RSS 피드를 준비 중입니다... 잠시만 기다려주세요."):
    generation_successful = generate_and_save_rss_feed_cached(RSS_FILE_PATH)

if generation_successful:
    st.success("RSS 피드가 최신 상태로 준비되었습니다.")
else:
    st.warning(
        "최신 RSS 피드를 생성하는 데 실패했습니다. "
        f"이전에 저장된 '{RSS_FILE_PATH}' 파일이 있다면 해당 내용을 표시합니다."
    )

# 생성되었거나 기존에 있던 RSS 파일 로드 시도
feed_data = load_feed_for_display(RSS_FILE_PATH)

if feed_data:
    if feed_data.entries:
        sorted_entries = sorted(
            feed_data.entries,
            key=lambda entry: entry.published_parsed if hasattr(entry, 'published_parsed') else (0,0,0,0,0,0,0,0,0),
            reverse=True
        )
        
        for entry in sorted_entries:
            with st.container():
                if hasattr(entry, 'title') and hasattr(entry, 'link'):
                    st.markdown(
                        f"""
                        <a href="{entry.link}" target="_blank" style="text-decoration: none; color: inherit;">
                            <h3>{entry.title}</h3>
                        </a>
                        """,
                        unsafe_allow_html=True
                    )
                elif hasattr(entry, 'title'):
                    st.markdown(f"<h3>{entry.title}</h3>", unsafe_allow_html=True)

                meta_info_parts = []
                if hasattr(entry, 'author') and entry.author:
                    meta_info_parts.append(f"👤 {entry.author}")

                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        utc_dt = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
                        kst_tz = datetime.timezone(datetime.timedelta(hours=9))
                        kst_dt = utc_dt.astimezone(kst_tz)
                        meta_info_parts.append(f"📅 {kst_dt.strftime('%Y년 %m월 %d일 %H:%M KST')}")
                    except Exception:
                        if hasattr(entry, 'published'):
                             meta_info_parts.append(f"📅 {entry.published}")
                elif hasattr(entry, 'published') and entry.published:
                    meta_info_parts.append(f"📅 {entry.published}")

                if meta_info_parts:
                    st.caption("  ·  ".join(meta_info_parts))

                if hasattr(entry, 'summary') and entry.summary:
                    with st.expander("요약 보기", expanded=False):
                        st.markdown(entry.summary, unsafe_allow_html=True)
                
                st.markdown("---")
    elif feed_data.bozo:
         st.warning("피드를 파싱했으나, 표시할 게시글이 없거나 피드 데이터에 문제가 있을 수 있습니다.")
    else:
        st.info("ℹ️ 피드에 표시할 게시글이 없습니다.")
elif not os.path.exists(RSS_FILE_PATH): # 생성도 실패했고, 기존 파일도 없는 경우
    st.error(
        f"'{RSS_FILE_PATH}' 파일이 존재하지 않고, 새로 생성하는 데도 실패했습니다. "
        "기사 피드를 표시할 수 없습니다. 사이트 구조가 변경되었거나 네트워크 문제가 있을 수 있습니다."
    )
else: # 파일은 존재하나 load_feed_for_display에서 None 반환 (심각한 파싱 오류 등)
    st.error(f"'{RSS_FILE_PATH}' 파일을 읽거나 파싱하는 데 실패했습니다. 파일이 손상되었을 수 있습니다.")


st.markdown("---")
st.markdown("<p style='text-align: center; color: grey; font-size: small;'>Neosherlock Article Feed | Powered by Streamlit</p>", unsafe_allow_html=True)