import streamlit as st
import json
import pandas as pd
import os
from datetime import datetime
from datetime import timedelta

from zoom_integration import get_schedules

import requests

import pytz

import altair as alt

CSV_FILE='data.csv'
JSON_FILE='data.json'

#
# All internal calculations are in UTC
# Convert to user-friendly timezones at IO
#

df_comparison=pd.DataFrame()
df_before=pd.DataFrame()
df_after=pd.DataFrame()

tab1,tab2,tab2b, tab3,tab4,tab5,tab6=st.tabs(["Main","Upload","Web Fetch","Date range","Overlaps","Busy","Daily"])

zoom_sessions={
'14FZQXqLRSODS33uQTVVaw':'AZ2',
'5uBBBmxkRs2ULd5cfs8Adw':'AZ5',
'atAAAIDOQYqcONrWd0oxxg':'AZ1',
'dZ6K_rnJTOO5S-jOUpXf3w':'AZ3',
'di6QjKDzTA-BsECJM-lqDA':'AZ7',
'j4IclWA4ScOUmP_grnbflg':'AZ4',
}

def create_csv(s):
    dataset=json.loads(s)
    da=dataset['data']
    me=dataset['data']['meetings']
    ne=dataset['data']['nextPageTokens']
    df_combined=pd.DataFrame()
    for ke,_ in me.items():
        upc=me[ke]['upcoming']
        ses=upc['sessions']
        print(f"{ke} upc-ses: {ses}")
        df_new=pd.DataFrame(ses)
        if not df_new.empty:
            df_new['start_time'] = pd.to_datetime(df_new['start_time'])
            df_new['end_time'] = df_new['start_time']+pd.to_timedelta(df_new['duration'], unit='m')
            df_combined = pd.concat([df_combined, df_new], ignore_index=True)
    print(f"{ke} df: \n{df_combined.info()}")
    df_combined.to_csv(CSV_FILE, index=False)
    return

def create_csv2(s):
    dataset=json.loads(s)
    me=dataset['meetings']
    df_combined=pd.DataFrame()
    for ke,_ in me.items():
        upc=me[ke]['upcoming']
        ses=upc['sessions']
        print(f"{ke} upc-ses: {ses}")
        df_new=pd.DataFrame(ses)
        if not df_new.empty:
            df_new['start_time'] = pd.to_datetime(df_new['start_time'])
            df_new['end_time'] = df_new['start_time']+pd.to_timedelta(df_new['duration'], unit='m')
            df_combined = pd.concat([df_combined, df_new], ignore_index=True)
    print(f"{ke} df: \n{df_combined.info()}")
    df_combined.to_csv(CSV_FILE, index=False)
    return

def find_overlaps(df):
    overlaps = []

    # Sort by hostid and start-time for easier processing
    new_df = df.copy()
    new_df = new_df.sort_values(by=['host_id', 'start_time', 'end_time'])

    # Iterate through each hostid
    for _, group in new_df.groupby('host_id'):
        for i in range(len(group)):
            session_i = group.iloc[i]
            for j in range(i+1, len(group)):
                session_j = group.iloc[j]
                # Check if sessions overlap: session_i end-time > session_j start-time and vice versa
                if session_i['end_time'] > session_j['start_time']:
                    overlaps.append({'host-id':session_i['host_id'], 
                                     'Topic 1':session_i['start_time'], 
                                     'Session 1':session_i['topic'],
                                     'Topic 2':session_j['topic'],
                                     'Session 2':session_j['start_time'],})
    return overlaps


def find_closest_record_before(host_id, df_combined, date_time, duration):
  if not isinstance(date_time, pd.Timestamp):
    date_time = pd.to_datetime(date_time)
  if df_combined['end_time'].dtype.tz is not None:
    #date_time = date_time.tz_localize('UTC')  # or use tz_convert('UTC') if it already has a timezone
    date_time = date_time.tz_convert('UTC')  # or use tz_localize('UTC') if it does not has a timezone

  #st.write(f"Date time is {date_time} with type {type(date_time)}")
  #st.write(f"Start time type is {df_combined['start_time'].apply(type)}")
  #st.write(f"End time type is {df_combined['end_time'].apply(type)}")
  df_filtered = df_combined[(df_combined['end_time'] <= date_time) & (df_combined['host_id'] == host_id)]
  if df_filtered.empty:
    return 'N.A.',None,14400
  closest_record = df_filtered.loc[df_filtered['start_time'].idxmax()]
  closest_end_time = closest_record['start_time'] + pd.Timedelta(minutes=closest_record['duration'])
  time_gap = date_time - closest_end_time
  return closest_record['topic'],closest_record['end_time'],time_gap.total_seconds()/60

def find_closest_record_after(host_id, df_combined, date_time, duration):
  if not isinstance(date_time, pd.Timestamp):
    date_time = pd.to_datetime(date_time)
  if df_combined['end_time'].dtype.tz is not None:
    #date_time = date_time.tz_localize('UTC')  # or use tz_convert('UTC') if it already has a timezone
    date_time = date_time.tz_convert('UTC')  # or use tz_localize('UTC') if it does not has a timezone

  #print(f"Date time is {date_time} with type {type(date_time)}")
  #print(f"Start time type is {df_combined['start_time'].apply(type)}")
  df_filtered = df_combined[(df_combined['start_time'] >= date_time) & (df_combined['host_id'] == host_id)]
  if df_filtered.empty:
    return 'N.A.',None,14400
  closest_record = df_filtered.loc[df_filtered['start_time'].idxmin()]

  end_time = date_time+ pd.Timedelta(minutes=duration)
  time_gap = closest_record['start_time'] - end_time
  return closest_record['topic'],closest_record['start_time'],time_gap.total_seconds()/60

def convert_date_time_from_pacific_to_utc(d,t): 
  dt = datetime.combine(d, t)
  pacific = pytz.timezone('US/Pacific')
  pacific_time = pacific.localize(dt)
  utc_time = pacific_time.astimezone(pytz.utc)
  return utc_time

def convert_utc_to_pacific_display(utc_time):
    if pd.isna(utc_time):
        return None
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)
    #print(f"UTC time is: {utc_time}")
    pacific = pytz.timezone('US/Pacific')
    pacific_time = utc_time.astimezone(pacific)
    formatted_pacific_time = pacific_time.strftime("%b %d, %I:%M %p")
    return formatted_pacific_time
   

def find_schedule(d,t,duration=60,w=0):
    global df_comparison, df_before, df_after
    #dt = datetime.datetime.combine(d+timedelta(weeks=w), t)
    dt = convert_date_time_from_pacific_to_utc(d+timedelta(weeks=w),t)
    df=pd.read_csv(CSV_FILE)
    df['host_id']=df['host_id'].replace(zoom_sessions)
    df['start_time'] = pd.to_datetime(df['start_time'])
    df['end_time'] = pd.to_datetime(df['end_time'])
    st.sidebar.write(f"{duration} mins for {convert_utc_to_pacific_display(dt)}")
    unique_hosts=df['host_id'].unique()
    #st.write(f"Unique hosts: {unique_hosts}")
    mylist=[]
    beforeList=[]
    afterList=[]
    for host in unique_hosts:
        #st.write(f"host: {host}")
        t1,r1,g1=find_closest_record_before(host,df,dt,duration)
        #st.write(f"{host}: closest before {dt} is {r1}")
        t2,r2,g2=find_closest_record_after(host,df,dt,duration)
        #st.write(f"{host}: closest after {dt} is {r2}")
        gmin=min(g1,g2)
        mylist.append({'host_id':host,'new_dt':dt,'new_duration':duration,
                       'before_topic':t1,'before_et':r1,'before_gap':g1,
                       'after_topic':t2,'after_st':r2,'after_gap':g2,
                       'min_gap':gmin})
        beforeList.append({'host_id':host,'dt':dt,'duration':duration,
                       'topic':t1,'et':r1,'gap':g1,})
        afterList.append({'host_id':host,'dt':dt,'duration':duration,
                       'topic':t2,'st':r2,'gap':g2,})
    df_comparison=pd.DataFrame(mylist)
    df_comparison.sort_values(by='min_gap',ascending=False,inplace=True)
    df_before=pd.DataFrame(beforeList)
    df_after=pd.DataFrame(afterList)

with tab1:
    if os.path.exists('data.csv'):
        col1,col2,col3,col4=st.columns(4)
        date=col1.date_input("Find Zoom for: ", value=None)
        time=col2.time_input("Time (Pacific)", value=None)
        duration=col3.number_input("Duration", value=60)
        repeat=col4.number_input("Repeat", value=1)
        if date and time and duration and repeat:
            df_combined=pd.DataFrame()
            df_combined_before=pd.DataFrame()
            df_combined_after=pd.DataFrame()
            for i in range(repeat):
              find_schedule(date,time,duration,i)
              df_combined=pd.concat([df_combined,df_comparison], ignore_index=True)
              df_combined_before=pd.concat([df_combined_before,df_before], ignore_index=True)
              df_combined_after=pd.concat([df_combined_after,df_after], ignore_index=True)
            # Now combine
            idx_before=df_combined_before.groupby('host_id')['gap'].idxmin()
            df_min_before=df_combined_before.loc[idx_before]
            df_min_before=df_min_before.reset_index(drop=True)
            idx_after=df_combined_after.groupby('host_id')['gap'].idxmin()
            df_min_after=df_combined_after.loc[idx_after]
            df_min_after=df_min_after.reset_index(drop=True)
            df_min=pd.merge(df_min_before,df_min_after,on='host_id',suffixes=('_before','_after'))
            df_min['min_gap'] = df_min[['gap_before', 'gap_after']].min(axis=1)
            # Old way
            fields=['host_id','min_gap','before_gap','after_gap','before_topic','before_et','after_topic','after_st']
            df_display_old=df_combined[fields].copy()
            df_display_old['before_et'] = df_display_old['before_et'].apply(convert_utc_to_pacific_display)
            df_display_old['after_st'] = df_display_old['after_st'].apply(convert_utc_to_pacific_display)
            df_display_old.rename(columns={'host_id':'Host','min_gap':'Minimum gap',
                                       'before_topic':'Topic 1','before_et':'End time 1',
                                       'after_topic':'Topic 2','after_st':'Start time 2',
                                       },inplace=True)
            #Now display
            fields=['host_id','min_gap','gap_before','gap_after','topic_before','et','topic_after','st']
            df_display_new=df_min[fields].copy()
            df_display_new['et'] = df_display_new['et'].apply(convert_utc_to_pacific_display)
            df_display_new['st'] = df_display_new['st'].apply(convert_utc_to_pacific_display)
            df_display_new.sort_values(by='min_gap',ascending=False,inplace=True)
            df_display_new.rename(columns={'host_id':'Host','min_gap':'Minimum gap',
                                       'topic_before':'Topic 1','et':'End time 1',
                                       'topic_after':'Topic 2','st':'Start time 2',
                                       },inplace=True)

            st.dataframe(df_display_new,hide_index=True)
            with st.sidebar.expander("Raw data"):
              st.dataframe(df_min,hide_index=True)
            with st.sidebar.expander("Old way"):
              st.dataframe(df_display_old,hide_index=True,use_container_width=False)
            with st.sidebar.expander("Details - Complete"):
               st.dataframe(df_combined_before)
               st.dataframe(df_combined_after)
            with st.sidebar.expander("Details - Min"):
               st.dataframe(df_min_before)
               st.dataframe(df_min_after)
    else:
        st.title("Please upload JSON first.")
        if st.button("Refresh"):
          st.rerun()

with tab2:
    uploaded_file = st.file_uploader(
        "Upload JSON file", accept_multiple_files=False
    )
    if uploaded_file is not None:
        file_contents=uploaded_file.getvalue().decode('utf-8')
        with open(JSON_FILE,'w') as f:
            f.write(file_contents)
            f.close()
        create_csv(file_contents)
    if st.button("Refresh!"):
     st.rerun()

with tab2b:
  if st.button("Fetch from Zoom API"):
    st.write("Fetching with Zoom API")
    d=get_schedules()
    if d:
    # Save the JSON response to a file
      with open(JSON_FILE, 'w') as file:
        file.write(json.dumps(d))
      st.write(f'Response data saved to {JSON_FILE}')
      with open(JSON_FILE,'r') as f:
        file_contents=f.read()
      create_csv2(file_contents)
    else:
      st.write(f"Failed to fetch data.")
    st.write("Completed fetching the Zoom API")


xxx="""
with tab2b:
  if st.button("Fetch from Web"):
    authcode=st.secrets['GLOBALZOOM_AUTH_CODE']
    url = 'https://apigateway.navigator.pyxeda.ai/dashboard-2.0/global-zoom-view?userIds=%5B%5D&meetingTypes=%5B%22upcoming%22,%22live%22%5D&limit=200'
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9',
        'authorization': authcode,
        'origin': 'https://my.aiclub.world',
        'priority': 'u=1, i',
        'referer': 'https://my.aiclub.world/',
        'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
    # Save the JSON response to a file
      with open(JSON_FILE, 'w') as file:
        file.write(response.text)
      st.write(f'Response data saved to {JSON_FILE}')
      with open(JSON_FILE,'r') as f:
        file_contents=f.read()
      create_csv(file_contents)
    else:
      st.write(f"Failed to fetch data. Status code: {response.status_code}")
"""

    
with tab3:
    df=pd.read_csv(CSV_FILE)
    df['host_id']=df['host_id'].replace(zoom_sessions)
    df['start_time'] = pd.to_datetime(df['start_time'])
    df['end_time'] = pd.to_datetime(df['end_time'])
    df_grouped=df.groupby('host_id').agg(
       host_id=('host_id','min'),
       count=('start_time','count'),
       min_st=('start_time','min'),
       max_st=('start_time','max'),
       )
    df_grouped['min_st'] = df_grouped['min_st'].apply(convert_utc_to_pacific_display)
    df_grouped['max_st'] = df_grouped['max_st'].apply(convert_utc_to_pacific_display)
    df_grouped.rename(columns={'min_st':'Earliest','max_st':'Latest',
                            'count':'Sessions',
                            },inplace=True)
    st.title("Session information available")
    unique_hosts=df['host_id'].unique()
    st.dataframe(df_grouped,hide_index=True)
    file_size=os.path.getsize(CSV_FILE)
    file_ts=datetime.fromtimestamp(os.path.getmtime(CSV_FILE))
    st.write(f"{file_size//1024} KB on {convert_utc_to_pacific_display(file_ts)} ")
    #st.rerun()

with tab4:
    overlaps=find_overlaps(df)
    if overlaps:
        st.write(f"Found {len(overlaps)} overlapping sessions")
        print("Overlapping Sessions Found:")
        df_overlaps=pd.DataFrame(overlaps)
        st.dataframe(df_overlaps, hide_index=True)
    else:
        st.title("No overlapping sessions found.")
        #host_selected = st.selectbox("Choose host",unique_hosts)
        #if host_selected:
        #  st.dataframe(df[df['host_id']==host_selected])

with tab5:
  st.title("Busy time intervals")
  df=pd.read_csv(CSV_FILE)
  df['host_id']=df['host_id'].replace(zoom_sessions)
  df['start_time'] = pd.to_datetime(df['start_time'])
  df['end_time'] = pd.to_datetime(df['end_time'])
  overall_start_time = df['start_time'].min().floor('h')
  overall_end_time = df['end_time'].max()
  hourly_intervals = pd.date_range(start=overall_start_time, end=overall_end_time, freq='h')
  result_df = pd.DataFrame({'interval': hourly_intervals})
  for hostid, group in df.groupby('host_id'):
    result_df[hostid] = 0 
    for i,interval in enumerate(hourly_intervals):
        # Check if the interval falls within any session for this host
        live = any((group['start_time'] <= interval) & (group['end_time'] > interval))
        if live:
           result_df.at[i,hostid]=1
  result_df['busy_hosts_count'] = result_df.iloc[:, 1:].sum(axis=1)
  result_df['interval'] = result_df['interval'] #.dt.strftime('%b %d %H:%M')
  chart = alt.Chart(result_df).mark_line(point=True).encode(
    x='interval:T',  # Time on the X axis
    y='busy_hosts_count:Q',  # Busy host count on the Y axis
    tooltip=['interval:T', 'busy_hosts_count:Q']  # Tooltips for interactivity
    ).properties(
    title='Number of Busy Hosts Over Time'
    )

  st.altair_chart(chart, use_container_width=True)
  st.dataframe(result_df, hide_index=True)
  if st.button("Refresh!!"):
    st.rerun()

with tab6:
  st.title("Daily sessions")
  df=pd.read_csv(CSV_FILE)
  df['host_id']=df['host_id'].replace(zoom_sessions)
  df['start_time'] = pd.to_datetime(df['start_time'])
  df['end_time'] = pd.to_datetime(df['end_time'])
  df['date'] = df['start_time'].dt.date
  daily_sessions_df = df.groupby('date').size().reset_index(name='session_count')
  chart = alt.Chart(daily_sessions_df).mark_bar().encode(
      x='date:T',  # Date on the X-axis
      y='session_count:Q',  # Number of sessions on the Y-axis
      tooltip=['date:T', 'session_count:Q']  # Tooltips for interactivity
  ).properties(
      title='Number of Sessions Per Day'
  )
  st.altair_chart(chart, use_container_width=True)
  st.dataframe(daily_sessions_df,hide_index=True)
  if st.button("Refresh it"):
     st.rerun()

