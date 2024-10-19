import streamlit as st
import json
import pandas as pd
import os
import datetime

CSV_FILE='data.csv'
JSON_FILE='data.json'

tab1,tab2,tab3=st.tabs(["Main","Upload","Configure"])

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

def find_closest_record_before(df_combined, date_time, host_id):
  if not isinstance(date_time, pd.Timestamp):
    date_time = pd.to_datetime(date_time)
  if df_combined['end_time'].dtype.tz is not None:
    date_time = date_time.tz_localize('UTC')  # or use tz_convert('UTC') if it already has a timezone

  #st.write(f"Date time is {date_time} with type {type(date_time)}")
  #st.write(f"Start time type is {df_combined['start_time'].apply(type)}")
  #st.write(f"End time type is {df_combined['end_time'].apply(type)}")
  df_filtered = df_combined[(df_combined['end_time'] <= date_time) & (df_combined['host_id'] == host_id)]
  if df_filtered.empty:
    return None
  closest_record = df_filtered.loc[df_filtered['start_time'].idxmax()]
  return closest_record['start_time']

def find_closest_record_after(df_combined, date_time, host_id):
  if not isinstance(date_time, pd.Timestamp):
    date_time = pd.to_datetime(date_time)
  if df_combined['end_time'].dtype.tz is not None:
    date_time = date_time.tz_localize('UTC')  # or use tz_convert('UTC') if it already has a timezone

  #print(f"Date time is {date_time} with type {type(date_time)}")
  #print(f"Start time type is {df_combined['start_time'].apply(type)}")
  df_filtered = df_combined[(df_combined['start_time'] > date_time) & (df_combined['host_id'] == host_id)]
  if df_filtered.empty:
    return None
  closest_record = df_filtered.loc[df_filtered['start_time'].idxmin()]
  return closest_record['start_time']

def find_schedule(d,t,duration=60):
    dt = datetime.datetime.combine(d, t)
    df=pd.read_csv(CSV_FILE)
    df['start_time'] = pd.to_datetime(df['start_time'])
    df['end_time'] = pd.to_datetime(df['end_time'])
    st.title("Finding schedule...")
    unique_hosts=df['host_id'].unique()
    st.write(f"Unique hosts: {unique_hosts}")
    for host in unique_hosts:
        st.write(f"host: {host}")
        r1=find_closest_record_before(df,dt,host)
        st.write(f"{host}: closest before {dt} is {r1}")
        r2=find_closest_record_after(df,dt,host)
        st.write(f"{host}: closest after {dt} is {r2}")

with tab1:
    if os.path.exists('data.csv'):
        date=st.date_input("Find Zoom for: ", value=None)
        time=st.time_input(" ", value=None, label_visibility="collapsed")
        if date and time:
            find_schedule(date,time)
    else:
        st.title("Please upload JSON first.")


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
    


with tab3:
    st.write("Configure App")
