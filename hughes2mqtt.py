from requests import get
from requests.exceptions import ConnectionError
from paho.mqtt.client import Client as mqtt
from paho.mqtt.publish import multiple as publish_multiple

import schedule
import time


def get_env_config():
    import os

    return {
        'rt_env': os.environ.get('RUNTIME_ENV', 'dev'),
        'mqtt': {
            'username': os.environ.get('MQTT_USERNAME', None),
            'password': os.environ.get('MQTT_PASSWORD', None),
            'hostname': os.environ.get('MQTT_HOSTNAME', 'localhost'),
            'root': '{0}/{1}'.format(
                os.environ.get('RUNTIME_ENV', 'dev'),
                os.environ.get('MQTT_ROOT', 'hughesnet').lstrip('/')
            )
        },
        'hughesnet': {
            'terminal_ip': os.environ.get('HUGHES_TERMINAL')
        }
    }


def get_default_map():
    return {
        'usage': 'home/usage',
        'led_dimmsing': 'system/led/dimming/enabled',
        'install_page': 'install/install_page',
        'terminal_info': 'system/terminal_info',
        'led': 'home/status/led',
        'lui_access_level': 'home/lui_access_level',
        'wifi_lan': 'system/wifi/lan',
        'association': 'home/status/association',
        'nsp_feature1': 'home/nsp_feature1',
        'nsp_links': 'install/nsp_links',
        'system_status': 'home/status/system',
        'status_wan': 'home/status/wan',
        'status_lan': 'home/status/lan',
        'status_summary': 'home/status/summary',
        'general_summary': 'home/general/summary',
        'status_sbc': 'home/status/sbc',
        'status_satellite': 'home/status/satellite',
        'cgn_stats': 'home/cgn/stats',
        'cgn_bypass': 'home/cgn/bypass/enabled',
        'wac_enabled': 'home/wac/isenabled'
    }


def get_mqtt_config(running_config=get_env_config()):
    mqtt_config = running_config['mqtt']
    mqtt_config['clientname'] = 'hughes2mqtt.{0}'.format(
        running_config['rt_env']
    )
    
    return mqtt_config

    
def get_terminal_page(ip, page):
    if page[0] == '/':
        page = page[1:]
        
    url = f'http://{ip}/api/{page}'
    js = get(url).json()

    assert isinstance(js, dict) and 'error' not in js.keys(), 'Did not receive javascript or error from terminal.'       
    
    if isinstance(js, list) and len(js) == 1:
        js = js[0]
    
    return js


def get_all_terminal_pages(term_ip, data_map=get_default_map()):
    tstate = {}
    
    for key in data_map.keys():
        page = data_map[key]
        try:
            tstate[key] = get_terminal_page(term_ip, page)
        except ConnectionError:
            pass
        except Exception as e:
            tstate[key] = f'{type(e)}'
            
    return tstate


def get_all_topics(status, base_path=''):
    returns = []

    if isinstance(status, list) and len(status) > 0:
        for x in range(0, len(status)):
            returns.extend(get_all_topics(status[x], f'{base_path}/{x}'))
    elif isinstance(status, dict) and len(status.keys()) > 0:
        for k in status.keys():
            returns.extend(get_all_topics(status[k], f'{base_path}/{k}'))
    else:
        returns = [(base_path, status)]

    return returns


def send_updates(updates, mqtt_config=get_mqtt_config()):
    mqtt_client = mqtt(mqtt_config['clientname'])
    mqtt_client.username_pw_set(mqtt_config['username'], mqtt_config['password'])
    mqtt_client.connect(mqtt_config['hostname'])
    mqtt_client.loop_start()
    [mqtt_client.publish(path, status) for path,status in updates]
    time.sleep(4)
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    
def send_multiple_updates(updates, mqtt_config=get_mqtt_config()):
    msgs = [{'topic': path, 'payload': status} for path, status in updates]

    # TODO - Need to handle no auth
    publish_multiple(
        msgs,
        auth={'username': mqtt_config['username'], 'password': mqtt_config['password']},
        hostname=mqtt_config['hostname']
    )

def job():
    print('Called Job')

    mqtt_config = get_mqtt_config()
    env_config = get_env_config()

    send_multiple_updates(get_all_topics(get_all_terminal_pages(env_config['hughesnet']['terminal_ip']), mqtt_config['root']))


if __name__ == '__main__':
    schedule.every(1).minutes.do(job)
    print(schedule.jobs)
    #print(get_env_config())

    while True:
        schedule.run_pending()
        time.sleep(1)
