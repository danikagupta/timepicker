import streamlit as st
import json
import pandas as pd
import os
import datetime

CSV_FILE='data.csv'
JSON_FILE='data.json'

df_comparison=pd.DataFrame()

tab1,tab2,tab3=st.tabs(["Main","Upload","Status"])

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

def find_closest_record_before(host_id, df_combined, date_time, duration):
  if not isinstance(date_time, pd.Timestamp):
    date_time = pd.to_datetime(date_time)
  if df_combined['end_time'].dtype.tz is not None:
    date_time = date_time.tz_localize('UTC')  # or use tz_convert('UTC') if it already has a timezone

  #st.write(f"Date time is {date_time} with type {type(date_time)}")
  #st.write(f"Start time type is {df_combined['start_time'].apply(type)}")
  #st.write(f"End time type is {df_combined['end_time'].apply(type)}")
  df_filtered = df_combined[(df_combined['end_time'] <= date_time) & (df_combined['host_id'] == host_id)]
  if df_filtered.empty:
    return None,0,14400
  closest_record = df_filtered.loc[df_filtered['start_time'].idxmax()]
  closest_end_time = closest_record['start_time'] + pd.Timedelta(minutes=closest_record['duration'])
  time_gap = date_time - closest_end_time
  return closest_record['start_time'],closest_record['duration'],time_gap.total_seconds()/60

def find_closest_record_after(host_id, df_combined, date_time, duration):
  if not isinstance(date_time, pd.Timestamp):
    date_time = pd.to_datetime(date_time)
  if df_combined['end_time'].dtype.tz is not None:
    date_time = date_time.tz_localize('UTC')  # or use tz_convert('UTC') if it already has a timezone

  #print(f"Date time is {date_time} with type {type(date_time)}")
  #print(f"Start time type is {df_combined['start_time'].apply(type)}")
  df_filtered = df_combined[(df_combined['start_time'] > date_time) & (df_combined['host_id'] == host_id)]
  if df_filtered.empty:
    return None,0,14400
  closest_record = df_filtered.loc[df_filtered['start_time'].idxmin()]

  end_time = date_time+ pd.Timedelta(minutes=duration)
  time_gap = closest_record['start_time'] - end_time
  return closest_record['start_time'],closest_record['duration'],time_gap.total_seconds()/60

def find_schedule(d,t,duration=60):
    global df_comparison
    dt = datetime.datetime.combine(d, t)
    df=pd.read_csv(CSV_FILE)
    df['host_id']=df['host_id'].replace(zoom_sessions)
    df['start_time'] = pd.to_datetime(df['start_time'])
    df['end_time'] = pd.to_datetime(df['end_time'])
    st.title(f"Finding schedule for {dt} - {duration} minutes")
    unique_hosts=df['host_id'].unique()
    #st.write(f"Unique hosts: {unique_hosts}")
    mylist=[]
    for host in unique_hosts:
        #st.write(f"host: {host}")
        r1,d1,g1=find_closest_record_before(host,df,dt,duration)
        #st.write(f"{host}: closest before {dt} is {r1}")
        r2,d2,g2=find_closest_record_after(host,df,dt,duration)
        #st.write(f"{host}: closest after {dt} is {r2}")
        gmin=min(g1,g2)
        mylist.append({'host_id':host,'new_dt':dt,'new_duration':duration,
                       'before_st':r1,'before_duration':d1,'before_gap':g1,
                       'after_st':r2,'after_duration':d2,'after_gap':g2,
                       'min_gap':gmin})
    df_comparison=pd.DataFrame(mylist)
    df_comparison.sort_values(by='min_gap',ascending=False,inplace=True)

with tab1:
    if os.path.exists('data.csv'):
        date=st.date_input("Find Zoom for: ", value=None)
        time=st.time_input(" ", value=None, label_visibility="collapsed")
        if date and time:
            find_schedule(date,time)
            fields=['host_id','min_gap','before_gap','after_gap','before_st','before_duration','after_st','after_duration']
            df_display=df_comparison[fields].copy()
            df_display.rename(columns={'host_id':'Host','min_gap':'Minimum gap'},inplace=True)
            #st.write('Rename complete')
            st.dataframe(df_display,hide_index=True,use_container_width=False)
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
    st.write("Status App")
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
    st.title("Aggregate stats")
    unique_hosts=df['host_id'].unique()
    st.dataframe(df_grouped,hide_index=True)
    #host_selected = st.selectbox("Choose host",unique_hosts)
    #if host_selected:
    #  st.dataframe(df[df['host_id']==host_selected])


