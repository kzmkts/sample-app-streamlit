# import time
from apiclient.discovery import build
import json
import pandas as pd
import numpy as np
import datetime
import dateutil.parser
import streamlit as st

with open('env.json') as f:
    env = json.load(f)

DEVELOPER_KEY = env['KEY']
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                developerKey=DEVELOPER_KEY)


def get_search_list(youtube, q, max_results, order):
    search_list = youtube.search().list(
        q=q,
        part="snippet",
        order=order,
        type='video',
        maxResults=max_results,
    ).execute()

    items_id = []
    items = search_list['items']
    for item in items:
        item_id = {}
        item_id['video_id'] = item['id']['videoId']
        item_id['channel_id'] = item['snippet']['channelId']
        items_id.append(item_id)
    df_serch_list = pd.DataFrame(items_id)

    return df_serch_list


def get_channels_list(df_serch_list):
    channel_ids = df_serch_list['channel_id'].unique().tolist()
    subscriber_list = youtube.channels().list(
        id=','.join(channel_ids),
        part='statistics',
        fields='items(id,statistics(subscriberCount))'
    ).execute()

    subscribers = []
    for item in subscriber_list['items']:
        subscriber = {}
        subscriber['channel_id'] = item['id']
        if 'subscriberCount' in item['statistics']:
            subscriber['subscriber_count'] = int(
                item['statistics']['subscriberCount'])
        else:
            subscriber['subscriber_count'] = 0
        subscribers.append(subscriber)

    df_subscriber = pd.DataFrame(subscribers)

    return df_subscriber


def get_videos_list(df_serch_list):
    video_ids = df_serch_list['video_id'].tolist()
    video_list = youtube.videos().list(
        id=','.join(video_ids),
        part='snippet,contentDetails,statistics',
        fields=('items(id,snippet(title,publishedAt),contentDetails(duration),'
                'statistics(viewCount,likeCount))')
    ).execute()

    videos_info = []
    items = video_list['items']
    JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
    for item in items:
        video_info = {}
        video_info['video_id'] = item['id']
        video_info['title'] = item['snippet']['title']
        video_info['published_at'] = dateutil.parser.parse(
            item['snippet']['publishedAt']).astimezone(JST).date()
        if 'likeCount' in item['statistics']:
            view_count = int(item['statistics']['viewCount'])
            like_count = int(item['statistics']['likeCount'])
            video_info['view_count'] = view_count
            video_info['like_count'] = like_count
        else:
            video_info['view_count'] = int(item['statistics']['viewCount'])
            video_info['like_count'] = 0
        videos_info.append(video_info)

    df_videos_info = pd.DataFrame(videos_info)

    return df_videos_info


@st.cache
def get_data(youtube, q='python', max_results=50, order='viewCount'):
    df_serch_list = get_search_list(youtube, q, max_results, order)
    df_subscriber = get_channels_list(df_serch_list)
    df_videos_info = get_videos_list(df_serch_list)

    df_results = pd.merge(left=df_serch_list,
                          right=df_subscriber, on='channel_id')
    df_results = pd.merge(left=df_results, right=df_videos_info, on='video_id')
    df_results['like_rate'] = np.divide(df_results['like_count'], df_results['view_count'], out=np.zeros_like(
        df_results['like_count'], dtype=np.float64), where=df_results['view_count'] != 0)*100
    df_results = df_results.loc[:, [
        'video_id', 'title', 'like_rate', 'view_count', 'subscriber_count', 'published_at']]

    return df_results


search_query = st.sidebar.text_input('検索クエリ', 'Python')
search_order_list = {
    'viewCount': '視聴回数',
    'date': 'アップロード日',
    'rating': '評価',
    'relevance': '関連度順'
}
search_order = st.sidebar.radio(
    '検索順', ('viewCount', 'date', 'rating', 'relevance'),
    format_func=lambda x: search_order_list.get(x)
)

st.title('youtube検索 + 0.00001要素')
st.markdown('### 選択中のパラメータ')
st.markdown(f"""
- 検索クエリ: {search_query}
- 検索順: {search_order_list[search_order]}
""")

df = get_data(youtube, q=search_query,
              max_results=50,  order=search_order)
df_field = st.dataframe(df.style.highlight_max(
    subset=['like_rate', 'view_count', 'subscriber_count'], color='pink'))


st.write("### 動画再生")
video_id = st.text_input('動画ID')
url = f"https://youtu.be/{video_id}"
video_btn = st.button('ビデオ表示')
video_field = st.empty()
if video_btn:
    if len(video_id):
        try:
            video_field.video(url)
        except:
            st.error('ビデオを表示できません')
