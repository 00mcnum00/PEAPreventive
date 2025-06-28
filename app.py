from flask import Flask, render_template, request
import pandas as pd
import os
import re
import glob

app = Flask(__name__)

def get_color_from_status(status_str):
    if not isinstance(status_str, str):
        return 'status-grey'
    status_str = status_str.strip()
    if status_str == 'Normal':
        return 'status-green'
    elif status_str == 'Warning Alert':
        return 'status-orange'
    elif status_str == 'Critical Alert':
        return 'status-red'
    else:
        return 'status-grey'

def load_data():
    base_path_pattern = 'Overall_Serial_Export_*_Recheck.xlsx - '
    def find_file(suffix):
        files = glob.glob(f'{base_path_pattern}{suffix}')
        if files:
            return sorted(files, reverse=True)[0]
        return None

    files = {
        'overall': find_file('Overall.csv'),
        'cards': find_file('Card Report.csv'),
        'subcards': find_file('SubCard Report.csv'),
        'sfps': find_file('Actual SFP.csv'),
        'frames': find_file('Frame Report.csv'),
        'all_serial': find_file('AllSerialNo.csv'),
        'links': find_file('link Report.csv')
    }
    
    column_maps = {
        'overall': {3: 'Node Name (NCE)', 7: 'Management IP (Loopback IP)', 6: 'Site Name (Confirmed)', 8: 'NE Type', 9: 'Access Network', 10: 'Region', 2: 'Data Updated'}, 
        'frames': {0: 'NE Name', 1: 'Subrack Name', 5: 'Software Version', 6: 'SN(Bar Code)', 12: 'PN(BOM Code)'}, 
        'cards': {0: 'NE Name', 1: 'Board Full Name', 3: 'Board Type', 9: 'Slot ID', 12: 'SN(Bar Code)', 22: 'PN(BOM Code)', 24: 'Description'}, 
        'subcards': {0: 'NE Name', 2: 'Subboard Full Name', 6: 'Slot Number', 7: 'Subslot Number', 10: 'SN(Bar Code)', 15: 'PN(BOM Code)', 13: 'Description'}, 
        'sfps': {0: 'SFP Serial No. (S/N)', 2: 'NE Name', 3: 'Port Name', 6: 'Receive Optical Power(dBm)', 9: 'Rx Power Status', 12: 'Transmit Optical Power(dBm)', 31: 'PN(BOM Code/Item)', 32: 'SFP-Type'}, 
        'all_serial': {11: 'Serial Number', 31: 'Phase (Ph.)', 32: 'Task Type', 36: 'Contract No.'}, 
        'links': {5: 'Source NE Name', 8: 'Source Port IP', 26: 'Source NE (Thai)', 27: 'Source Display Port', 28: 'So SFP-Type', 38: 'Source S/N Actual', 10: 'Sink NE', 13: 'Sink Port IP', 29: 'Sink NE (Thai)', 30: 'Sink Display Port', 31: 'Sink SFP-Type', 45: 'Sink S/N Actual'}
    }

    skip_rows_map = {'overall': 1, 'cards': 3, 'subcards': 3, 'sfps': 8, 'frames': 3, 'all_serial': 1, 'links': 3}
    dataframes = {}
    print("กำลังโหลดข้อมูล CSV...")
    try:
        update_date = "N/A"
        overall_file_path = files['overall']
        if overall_file_path and os.path.exists(overall_file_path):
            try:
                df_header = pd.read_csv(overall_file_path, header=None, nrows=1, on_bad_lines='skip')
                if not df_header.empty and len(df_header.columns) > 2:
                    update_date = df_header.iloc[0, 2]
            except Exception as e:
                print(f"ไม่สามารถอ่านวันที่จากไฟล์ Overall ได้: {e}")
        
        for name, file_path in files.items():
            if file_path and os.path.exists(file_path):
                print(f"กำลังโหลด: {file_path}")
                df = pd.read_csv(file_path, header=None, skiprows=skip_rows_map.get(name, 0), on_bad_lines='skip', dtype=str).fillna('')
                current_map = column_maps.get(name, {})
                valid_rename_dict = {k: v for k, v in current_map.items() if k in df.columns}
                df = df.rename(columns=valid_rename_dict)
                dataframes[name] = df[list(valid_rename_dict.values())]
            else: 
                print(f"คำเตือน: ไม่พบไฟล์สำหรับ '{name}'")
                dataframes[name] = pd.DataFrame()
    except Exception as e: print(f"เกิดข้อผิดพลาด: {e}")
    
    dataframes['update_date'] = update_date
    return dataframes

DATA = load_data()
print("โหลดข้อมูลทั้งหมดเรียบร้อยแล้ว!")

def get_details_from_serial(serial_no, df_all_serial):
    info = {'phase': 'N/A', 'remark': '', 'contract_no': 'N/A'}
    if df_all_serial is None or df_all_serial.empty or not serial_no or serial_no == 'N/A': return info
    search_sn = str(serial_no).strip()
    match = df_all_serial[df_all_serial['Serial Number'].astype(str).str.strip() == search_sn]
    if not match.empty:
        info['phase'] = match.iloc[0].get('Phase (Ph.)', 'N/A')
        info['contract_no'] = match.iloc[0].get('Contract No.', 'N/A')
        if match.iloc[0].get('Task Type') == 'Spare': info['remark'] = '(Spare)'
    return info

def get_link_info(sfp_serial, df_links):
    default_info = {"local_ip": "N/A", "direction_string": "Link not found"}
    if df_links is None or df_links.empty or not sfp_serial or sfp_serial == 'N/A': return default_info
    search_sn = str(sfp_serial).strip()
    if 'Source S/N Actual' in df_links.columns:
        source_match = df_links[df_links['Source S/N Actual'].str.strip() == search_sn]
        if not source_match.empty:
            row = source_match.iloc[0]
            direction_str = f"{row.get('Sink NE', '')} ({row.get('Sink NE (Thai)', row.get('Sink NE', ''))}) (IP: {row.get('Sink Port IP', 'N/A')}) Port: {row.get('Sink Display Port', '')} (SFP: {row.get('Sink SFP-Type', 'N/A')})"
            return {"local_ip": row.get('Source Port IP', 'N/A'), "direction_string": direction_str}
    if 'Sink S/N Actual' in df_links.columns:
        sink_match = df_links[df_links['Sink S/N Actual'].str.strip() == search_sn]
        if not sink_match.empty:
            row = sink_match.iloc[0]
            direction_str = f"{row.get('Source NE Name', '')} ({row.get('Source NE (Thai)', row.get('Source NE Name', ''))}) (IP: {row.get('Source Port IP', 'N/A')}) Port: {row.get('Source Display Port', '')} (SFP: {row.get('So SFP-Type', 'N/A')})"
            return {"local_ip": row.get('Sink Port IP', 'N/A'), "direction_string": direction_str}
    return default_info

def build_page_layout(ne_name, data, device_info):
    layout_info = {"frame_info": None, "chassis_layout": {}, "sfp_layout": {"left": [], "right": []}, "layout_name": "DEFAULT"}
    ne_name_lower = ne_name.lower()
    ne_type = device_info.get('NE Type', '')
    
    CHASSIS_ALIAS_MAP = {
        'NE08E-S6E': 'NE08E-S6',
        'OptiX OSN 1800': 'OSN1800',
        'OptiX OSN 1800 II TP': 'OSN1800',
        'NE40E-X3(V8)': 'NE40E_X3',
        'NE40E-X3A(V8)': 'NE40E_X3A',
        'NetEngine 8000 M14': 'NE8000_M14'
    }
    layout_type = CHASSIS_ALIAS_MAP.get(ne_type, ne_type)
    
    layout_map = {}
    if layout_type == 'NE08E-S6' or layout_type == 'OSN1800':
        layout_info["layout_name"] = "OSN1800"
        layout_map = { "col1_top": ["10"], "col1_bottom": ["9"], "col2": ["11"], "col3": ["7", "5", "3", "1"], "col4": ["8", "6", "4", "2"] }
    elif layout_type == 'NE40E_X3':
        layout_info["layout_name"] = "NE40E_X3"
        layout_map = {
            "slot1": ["1"], "slot2": ["2"], "slot3": ["3"], "slot4": ["4"], "slot5": ["5"],
            "slot8": ["8"], "slot9": ["9"], "slot10": ["10"]
        }
    elif layout_type == 'NE40E_X3A':
        layout_info["layout_name"] = "NE40E_X3A"
        layout_map = {
            "slot10": ["10"],
            "slot1_main": ["1"], 
            "slot1_sub": ["1_sub"], 
            "slot2_main": ["2"], 
            "slot2_sub": ["2_sub"], 
            "slot3_main": ["3"],
            "slot3_sub": ["3_sub"],
            "slot4": ["4"], "slot5": ["5"], "slot8": ["8"], "slot9": ["9"]
        }
    elif layout_type == 'NE8000_M14':
        layout_info["layout_name"] = "NE8000_M14_LAYOUT"
        layout_map = {
            "slot13": ["13"], "slot14": ["14"],
            "slot11": ["11"], "slot12": ["12"],
            "slot9": ["9"], "slot10": ["10"],
            "slot7": ["7"], "slot8": ["8"],
            "slot18": ["18"], "slot16": ["16"],
            "slot17": ["17"], "slot15": ["15"],
            "slot5": ["5"], "slot6": ["6"],
            "slot3": ["3"], "slot4": ["4"],
            "slot1": ["1"], "slot2": ["2"],
            "slot19": ["19"]
        }
    else:
        layout_info["layout_name"] = "M6_DEFAULT"
        layout_map = { "col1": ["7", "5", "3", "1"], "col2": ["8", "6", "4", "2"], "col3": ["11"], "col4_top": ["10"], "col4_bottom": ["9"] }

    df_frames = data.get('frames'); df_cards = data.get('cards'); df_subcards = data.get('subcards');
    df_sfps = data.get('sfps'); df_all_serial = data.get('all_serial'); df_links = data.get('links')
    
    if df_frames is not None and 'NE Name' in df_frames.columns:
        ne_frames = df_frames[df_frames['NE Name'].str.strip().str.lower() == ne_name_lower]
        if not ne_frames.empty:
            frame_row = ne_frames.iloc[0]
            sn_val = frame_row.get('SN(Bar Code)', 'N/A').strip()
            details_data = get_details_from_serial(sn_val, df_all_serial)
            layout_info["frame_info"] = { 'name': frame_row.get('Subrack Name', 'N/A'), 'sn': sn_val, 'pn': frame_row.get('PN(BOM Code)', 'N/A'), 'phase': details_data.get('phase', 'N/A'), 'contract_no': details_data.get('contract_no', 'N/A') }
            device_info['Software Version'] = frame_row.get('Software Version', 'N/A')
            
    chassis_slots_map = {str(i): {"slot_number": str(i), "data": None} for i in range(1, 20)}
    if layout_type == 'NE40E_X3A':
        chassis_slots_map['1_sub'] = {"slot_number": "1 (Sub-Card)", "data": None}
        chassis_slots_map['2_sub'] = {"slot_number": "2 (Sub-Card)", "data": None}
        chassis_slots_map['3_sub'] = {"slot_number": "3 (Sub-Card)", "data": None}
        
    if df_cards is not None and 'NE Name' in df_cards.columns:
        cards_in_ne = df_cards[df_cards['NE Name'].str.strip().str.lower() == ne_name_lower]
        for _, card_row in cards_in_ne.iterrows():
            slot_id = card_row.get('Slot ID', '').strip()
            if 'CFCARD' in str(card_row.get('Board Type', '')).upper(): continue
            
            if slot_id and slot_id in chassis_slots_map:
                sn_val = card_row.get('SN(Bar Code)', 'N/A').strip()
                details_data = get_details_from_serial(sn_val, df_all_serial)
                card_data = {
                    "board_type": card_row.get('Board Type', 'N/A'),
                    "pn": card_row.get('PN(BOM Code)', 'N/A'), "sn": sn_val,
                    "phase": details_data.get('phase', 'N/A'), "contract_no": details_data.get('contract_no', 'N/A'),
                    "description": card_row.get('Description', 'N/A')
                }
                chassis_slots_map[slot_id]["data"] = card_data

    if df_subcards is not None and 'NE Name' in df_subcards.columns:
        subcards_in_ne = df_subcards[df_subcards['NE Name'].str.strip().str.lower() == ne_name_lower]
        
        if layout_type == 'NE40E_X3A':
            for slot_num_str in ['1', '2', '3']:
                subcard_match = subcards_in_ne[subcards_in_ne['Slot Number'].str.strip() == slot_num_str]
                
                if not subcard_match.empty:
                    card_row = subcard_match.iloc[0]
                    sn_val = card_row.get('SN(Bar Code)', 'N/A').strip()
                    details_data = get_details_from_serial(sn_val, df_all_serial)
                    
                    card_data = {
                        "board_type": card_row.get('Subboard Full Name', 'N/A'),
                        "pn": card_row.get('PN(BOM Code)', 'N/A'), 
                        "sn": sn_val,
                        "phase": details_data.get('phase', 'N/A'), 
                        "contract_no": details_data.get('contract_no', 'N/A'),
                        "description": card_row.get('Description', 'N/A')
                    }
                    
                    sub_slot_key = f"{slot_num_str}_sub"
                    if sub_slot_key in chassis_slots_map:
                        chassis_slots_map[sub_slot_key]["data"] = card_data
        
        elif layout_type not in ['NE40E_X3']:
             for _, card_row in subcards_in_ne.iterrows():
                slot_id = card_row.get('Subslot Number', '').strip()
                if slot_id and slot_id in chassis_slots_map and not chassis_slots_map[slot_id].get("data"):
                    sn_val = card_row.get('SN(Bar Code)', 'N/A').strip()
                    details_data = get_details_from_serial(sn_val, df_all_serial)
                    card_data = {
                        "board_type": card_row.get('Subboard Full Name', 'N/A'),
                        "pn": card_row.get('PN(BOM Code)', 'N/A'), "sn": sn_val,
                        "phase": details_data.get('phase', 'N/A'), "contract_no": details_data.get('contract_no', 'N/A'),
                        "description": card_row.get('Description', 'N/A')
                    }
                    chassis_slots_map[slot_id]["data"] = card_data
                
    layout_info["chassis_layout"] = {key: [chassis_slots_map.get(slot_id) for slot_id in slots if slot_id in chassis_slots_map] for key, slots in layout_map.items()}
    
    if df_sfps is not None and 'NE Name' in df_sfps.columns:
        sfps_in_ne = df_sfps[df_sfps['NE Name'].str.strip().str.lower() == ne_name_lower]
        for _, sfp_row in sfps_in_ne.iterrows():
            port_name = sfp_row.get('Port Name', '').strip()
            port_slot_id, port_num_id = None, None
            match = re.search(r'\D*(\d+)/(\d+)/(\d+)', port_name)
            if match:
                port_slot_id = match.group(2) if not ne_type.startswith('NE40E') else match.group(1); port_num_id = int(match.group(3))
            if port_slot_id and port_slot_id.isdigit():
                sn_val = sfp_row.get('SFP Serial No. (S/N)', 'N/A').strip()
                details_data = get_details_from_serial(sn_val, df_all_serial); link_data = get_link_info(sn_val, df_links)
                
                status_val = sfp_row.get('Rx Power Status', '')
                sfp_status_color = get_color_from_status(status_val)
                
                sfp_details = {
                    'port_name': port_name, 'slot_id': int(port_slot_id), 'port_id': port_num_id, 'status_color': sfp_status_color,
                    'sfp_type': sfp_row.get('SFP-Type','N/A'), 'pn': sfp_row.get('PN(BOM Code/Item)','N/A'), 'sn': sn_val,
                    'phase': details_data.get('phase', 'N/A'), 'contract_no': details_data.get('contract_no', 'N/A'),
                    'local_ip': link_data.get('local_ip', 'N/A'), 'tx_power': sfp_row.get('Transmit Optical Power(dBm)','N/A'),
                    'rx_power': sfp_row.get('Receive Optical Power(dBm)','N/A'), 'direction': link_data.get('direction_string', 'N/A')
                }
                if int(port_slot_id) % 2 != 0: layout_info['sfp_layout']['left'].append(sfp_details)
                elif int(port_slot_id) <= 8: layout_info['sfp_layout']['right'].append(sfp_details)
        layout_info['sfp_layout']['left'].sort(key=lambda x: (-x.get('slot_id', 99), x.get('port_id', 99)))
        layout_info['sfp_layout']['right'].sort(key=lambda x: (-x.get('slot_id', 99), x.get('port_id', 99)))
    return layout_info

@app.route('/', methods=['GET', 'POST'])
def index():
    search_query = ""; device_info = None; page_layout = {} 
    update_date = DATA.get('update_date', 'N/A')
    if request.method == 'POST':
        search_query = request.form.get('query', '').strip()
        if search_query:
            df_overall = DATA.get('overall')
            if df_overall is not None and not df_overall.empty:
                required_cols = ['Node Name (NCE)', 'Management IP (Loopback IP)', 'Site Name (Confirmed)']
                if all(col in df_overall.columns for col in required_cols):
                    condition = (df_overall['Node Name (NCE)'].str.strip().str.lower() == search_query.lower()) | (df_overall['Management IP (Loopback IP)'].str.strip().str.lower() == search_query.lower()) | (df_overall['Site Name (Confirmed)'].str.strip().str.lower() == search_query.lower())
                    search_result = df_overall[condition].head(1)
                    if not search_result.empty:
                        device_info = search_result.iloc[0].to_dict()
                        canonical_ne_name = device_info.get('Node Name (NCE)')
                        if canonical_ne_name: page_layout = build_page_layout(canonical_ne_name, DATA, device_info)
    return render_template('index.html', search_query=search_query, device_info=device_info, page_layout=page_layout, update_date=update_date)

if __name__ == '__main__':
    app.run(debug=True)