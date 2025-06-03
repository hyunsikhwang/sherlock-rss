# app.py

import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime

# ————————————————
# 1) 아카이브 페이지에서 기사 URL 목록 가져오기
# ————————————————
def fetch_archive_urls(archive_url):
    resp = requests.get(archive_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    article_links = set()
    for link in soup.find_all('a', href=True):
        href = link['href']
        # https://www.neosherlock.com/archives/숫자 형태만 골라내기
        if re.match(r'https?://www\.neosherlock\.com/archives/\d+$', href):
            article_links.add(href)
    return list(article_links)


# ————————————————
# 2) 개별 기사 페이지에서 제목, 기자명, 본문, 게시일, 링크 추출
# ————————————————
def parse_article(article_url):
    resp = requests.get(article_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # 2-1) 제목 (<h1> 태그)
    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else 'No Title'
    
    # 2-2) 기자명(meta 속성 또는 클래스 탐색)
    author = 'Unknown'
    author_meta = soup.find('meta', {'property': 'article:author'})
    if author_meta and author_meta.get('content'):
        author = author_meta['content']
    else:
        author_tag = soup.find(class_=re.compile(r'author|byline', re.I))
        if author_tag:
            author = author_tag.get_text(strip=True)
    
    # 2-3) 게시일(meta 속성)
    pub_date = None
    date_meta = soup.find('meta', {'property': 'article:published_time'})
    if date_meta and date_meta.get('content'):
        try:
            dt = datetime.fromisoformat(date_meta['content'].replace('Z', '+00:00'))
            pub_date = format_datetime(dt)  # RFC2822 형식으로 변환
        except Exception:
            pub_date = None
    
    # 2-4) 본문(내용) 추출
    content = ''
    content_div = soup.find('div', class_=re.compile(r'entry-content|post-content', re.I))
    if content_div:
        content = content_div.get_text(separator='\n', strip=True)
    else:
        # fallback: 모든 <p> 태그를 합쳐서 본문으로 사용
        paragraphs = soup.find_all('p')
        content = '\n'.join(p.get_text(strip=True) for p in paragraphs)
    
    return {
        'title': title,
        'author': author,
        'pub_date': pub_date,
        'content': content,
        'link': article_url
    }


# ————————————————
# 3) RSS XML 생성 함수
# ————————————————
def generate_rss(feeds, site_title, site_link, site_description):
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    
    ET.SubElement(channel, 'title').text = site_title
    ET.SubElement(channel, 'link').text = site_link
    ET.SubElement(channel, 'description').text = site_description
    ET.SubElement(channel, 'lastBuildDate').text = format_datetime(datetime.utcnow())
    
    for feed in feeds:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = feed['title']
        ET.SubElement(item, 'link').text = feed['link']
        ET.SubElement(item, 'description').text = feed['content']
        if feed['author']:
            ET.SubElement(item, 'author').text = feed['author']
        if feed['pub_date']:
            ET.SubElement(item, 'pubDate').text = feed['pub_date']
    
    return ET.tostring(rss, encoding='utf-8', xml_declaration=True)


# ————————————————
# 4) RSS 파일 생성 및 feeds 리스트 반환
# ————————————————
def generate_and_save_rss():
    archive_url = 'https://www.neosherlock.com/archives'
    
    # 4-1) 아카이브 URL 목록 가져오기
    article_urls = fetch_archive_urls(archive_url)
    
    # 4-2) 각 기사 파싱
    feeds = []
    for url in article_urls:
        try:
            article_data = parse_article(url)
            feeds.append(article_data)
        except Exception:
            # 파싱 실패 시 건너뜀
            continue
    
    # 4-3) RSS XML 생성
    rss_xml = generate_rss(
        feeds,
        site_title='셜록 Archives',
        site_link=archive_url,
        site_description='네오셜록 아카이브 RSS 피드'
    )
    
    # 4-4) 파일로 저장
    file_path = 'neosherlock_rss.xml'
    with open(file_path, 'wb') as f:
        f.write(rss_xml)
    
    return feeds


# ————————————————
# 5) RSS XML을 파싱해서 화면 출력용 리스트 생성
# (이전 단계의 feeds를 그대로 사용해도 되지만,
#   XML 저장 확인 차원에서 다시 파싱하는 구조도 가능)
# ————————————————
def load_feeds_from_file(path):
    tree = ET.parse(path)
    root = tree.getroot()
    channel = root.find('channel')
    items = channel.findall('item')
    
    feeds = []
    for item in items:
        title = item.find('title').text or "No Title"
        link = item.find('link').text or ""
        description = item.find('description').text or ""
        author = item.find('author').text if item.find('author') is not None else ""
        pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
        
        feeds.append({
            'title': title,
            'link': link,
            'description': description,
            'author': author,
            'pub_date': pub_date
        })
    return feeds


# ————————————————
# Streamlit UI
# ————————————————
def main():
    st.set_page_config(page_title="셜록 Archive Feed", layout="centered")
    st.title("🔎 셜록 아카이브 실시간 Feed")
    st.write("앱 실행 시 자동으로 최신 아카이브를 크롤링하여 RSS를 생성하고, 간결한 디자인으로 보여드립니다.")
    
    # 5-1) RSS 파일 생성
    with st.spinner("네오셜록 아카이브에서 기사 데이터를 가져와 RSS 파일 생성 중..."):
        try:
            feeds = generate_and_save_rss()
            file_path = 'neosherlock_rss.xml'
        except Exception as e:
            st.error(f"RSS 생성 중 오류가 발생했습니다:\n{e}")
            return
    
    # 5-2) 생성된 XML을 다시 파싱하여 화면 출력용 리스트 확보
    try:
        display_feeds = load_feeds_from_file(file_path)
    except Exception as e:
        st.error(f"생성된 RSS XML 파싱 중 오류가 발생했습니다:\n{e}")
        return
    
    st.success("✅ RSS 파일 생성 및 파싱 완료!")
    st.markdown("---")
    
    # 5-3) 각 기사(item)를 화면에 출력
    for feed in display_feeds:
        st.markdown(f"## [{feed['title']}]({feed['link']})")
        
        # 기자명 & 게시일
        meta_parts = []
        if feed['author']:
            meta_parts.append(f"✍️ **기자**: {feed['author']}")
        if feed['pub_date']:
            meta_parts.append(f"🗓️ **게시일**: {feed['pub_date']}")
        if meta_parts:
            st.markdown("  ".join(meta_parts))
        
        # 본문 스니펫 (300자까지)
        snippet = feed['description'].strip()
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        st.write(snippet)
        
        st.markdown("---")


if __name__ == "__main__":
    main()
