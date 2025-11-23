import pandas as pd
from datetime import time
import time
from osm_api import osm_calls

def main():

    all_time_terms = [
                      {'section_name':'Smithies' , 'section':'12137', 'term':'534848', 'section_type':'beavers'},
                      {'section_name':'Skidmore' , 'section':'12049', 'term':'454422', 'section_type':'beavers'},
                      {'section_name':'Longmore' , 'section':'818'  , 'term':'454420', 'section_type':'cubs'},
                      {'section_name':'Wilson'   , 'section':'12783', 'term':'454424', 'section_type':'cubs'},
                      {'section_name':'Gibraltar', 'section':'2302' , 'term':'454426', 'section_type':'scouts'},
                      {'section_name':'Salamanca', 'section':'2303' , 'term':'454425', 'section_type':'scouts'}
    ]
    
    df_all = pd.DataFrame()

    for all_time_term in all_time_terms:
        attendance_table_columns = osm_calls.get_attendance_structure(all_time_term['section'], all_time_term['term'], all_time_term['section_type'])
        attendance_data =  osm_calls.get_attendance(all_time_term['section'], all_time_term['term'], all_time_term['section_type'])
        
        df_columns = pd.DataFrame(columns=attendance_table_columns)
        df_data = pd.DataFrame(data = attendance_data['items'])
        df = pd.concat((df_columns,df_data))
        print(df.head(10))
        df.to_csv('output/'+'attendance_' + all_time_term['section_name'] + '_' + time.strftime("%Y-%m-%d-%H%M%S") + '.csv')

        df_all = pd.concat((df_all,df))

    
    df_all = df_all.reindex(sorted(df_all.columns), axis=1)
    df_all.to_csv('output/'+'attendance_All_' + time.strftime("%Y-%m-%d-%H%M%S") + '.csv')

if __name__ == '__main__':
    main()