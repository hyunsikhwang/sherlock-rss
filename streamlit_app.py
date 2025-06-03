import streamlit as st
import feedparser
import datetime
import os

# --- Page Configuration ---
# This should be the first Streamlit command in your script.
st.set_page_config(
    page_title="셜록 아티클 피드",
    page_icon="📰",  # You can use an emoji or a URL to a .png file
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Constants ---
# Assumes the RSS file is in the same directory as this script.
# When deploying to Streamlit Cloud, ensure this file is in your GitHub repo.
RSS_FILE_PATH = "neosherlock_feed_final.xml"

# --- Helper Functions ---
def load_feed(file_path):
    """Loads and parses the RSS feed from a local file."""
    if not os.path.exists(file_path):
        st.error(f"🚨 RSS 파일({file_path})을 찾을 수 없습니다. 파일이 올바른 위치에 있는지 확인해주세요.")
        return None
    try:
        feed = feedparser.parse(file_path)
        # Check if parsing was successful (bozo bit is 0 for success)
        if feed.bozo:
            st.warning(f"⚠️ RSS 피드 파싱 중 일부 문제가 발생했을 수 있습니다: {feed.bozo_exception}")
            # Continue processing even if there are non-critical parsing issues
        return feed
    except Exception as e:
        st.error(f"🚨 RSS 파일을 읽거나 파싱하는 중 심각한 오류 발생: {e}")
        return None

# --- Main Application UI ---
st.title("📰 셜록 아티클 피드")
st.caption(f"'{RSS_FILE_PATH}' 파일에서 기사를 읽어옵니다.")
st.markdown("---")

feed_data = load_feed(RSS_FILE_PATH)

if feed_data:
    if feed_data.entries:
        # Sort entries by publication date (descending - newest first)
        # feedparser converts dates to UTC time.struct_time in 'published_parsed'
        sorted_entries = sorted(
            feed_data.entries,
            key=lambda entry: entry.published_parsed if hasattr(entry, 'published_parsed') else (0,0,0,0,0,0,0,0,0), # fallback for missing date
            reverse=True
        )
        
        for entry in sorted_entries:
            with st.container():
                # Title as a clickable link, styled minimally
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


                # Metadata: Author and Publication Date
                meta_info_parts = []
                if hasattr(entry, 'author') and entry.author:
                    meta_info_parts.append(f"👤 {entry.author}")

                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        # feedparser stores 'published_parsed' as a UTC time.struct_time
                        utc_dt = datetime.datetime(*entry.published_parsed[:6], tzinfo=datetime.timezone.utc)
                        kst_tz = datetime.timezone(datetime.timedelta(hours=9))
                        kst_dt = utc_dt.astimezone(kst_tz)
                        meta_info_parts.append(f"📅 {kst_dt.strftime('%Y년 %m월 %d일 %H:%M KST')}")
                    except Exception: # Fallback for any parsing/conversion error
                        if hasattr(entry, 'published'):
                             meta_info_parts.append(f"📅 {entry.published}")
                elif hasattr(entry, 'published') and entry.published: # Fallback if 'published_parsed' is missing
                    meta_info_parts.append(f"📅 {entry.published}")

                if meta_info_parts:
                    st.caption("  ·  ".join(meta_info_parts))

                # Summary/Description
                if hasattr(entry, 'summary') and entry.summary:
                    with st.expander("요약 보기", expanded=False): # Start collapsed
                        st.markdown(entry.summary, unsafe_allow_html=True) # Allow HTML if summary contains it
                
                st.markdown("---") # Visual separator between articles
    elif feed_data.bozo: # Feed was parsed but might have issues, and no entries
         st.warning("피드를 파싱했으나, 표시할 게시글이 없거나 피드 데이터에 문제가 있을 수 있습니다.")
    else: # Feed object exists but no entries (and not bozo)
        st.info("ℹ️ 피드에 표시할 게시글이 없습니다. RSS 파일이 비어있을 수 있습니다.")
# else: load_feed function already displayed an error if feed_data is None

# Minimal footer (optional)
st.markdown("---")
st.markdown("<p style='text-align: center; color: grey; font-size: small;'>Neosherlock Article Feed | Powered by Streamlit</p>", unsafe_allow_html=True)