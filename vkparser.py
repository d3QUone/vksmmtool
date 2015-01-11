import requests
import json
import os
import time
from datetime import datetime
import sqlite3


def get_out_db(statement):
    try:
        conn = sqlite3.connect('base.db')
        c = conn.cursor()
        res = c.execute(statement).fetchall()
        conn.close()
        return res
    except Exception as e:
        print "get_out_db error:", e
        return []
    

def save_into_db(statement):
    try:
        conn = sqlite3.connect('base.db')
        c = conn.cursor()
        c.execute(statement)
        conn.commit()
        conn.close()
    except Exception as e:
        print "save_into_db error:", e


# request interface
def getA(group_id, offset=0, count=100):
    url = "https://api.vk.com/method/wall.get"
    data = {
        "owner_id": "-" + str(group_id),
        "offset": offset,
        "count": count,
        "v": "5.27"
        }
    res = requests.get(url, params = data)
    try:
        if "response" in res.json().keys():
            return res.json()["response"]
        else:
            print "fuck:" + str(res.json())#['error']['error_msg'])
            return {"items":[], "count":0}
    except Exception as ex:
        print "Requests error:", ex
        return {"items":[], "count":0}


def full_cycle():
    # for stats
    t = datetime.now()

    all_group_IDS = get_out_db('select group_id from groups')
    print "Sum of groups:", len(all_group_IDS), " (with repeats)"
    group_list = []
    for group_id_tuple in all_group_IDS:
        group_id = group_id_tuple[0]
        if group_id not in group_list:
            group_list.append(group_id)
    
    print "I'm going to scan", len(group_list), "unique groups"
    print group_list
    glob = 0
    for group_id in group_list:
        # delete old posts
        save_into_db('delete from postinfo where group_id = {0}'.format(group_id))
        
        screen_name = get_out_db('select screen_name from groups where group_id = {0}'.format(group_id))[0][0]
        #print "screen_name:", screen_name
        
        errors = 0
        ret = getA(group_id, 0, 1)
        count = ret['count']
        while count == 0 and errors < 3:
            ret = getA(group_id, 0, 1)
            count = ret['count']
            errors += 1
            print "error1: ", errors 
            time.sleep(0.5)
            
        print "\nscreen_name:", screen_name, ", group_id:", group_id, ", nums to parse:", str(count)
        
        offset = count//100 + 1
        output = []
        for i in range(0, offset):
            errors = 0
            posts = getA(group_id, i*100, 100)
            while count == 0 and errors < 3:
                posts = getA(group_id, i*100, 100)
                count = ret['count']
                errors += 1
                print "error2: ", errors
                time.sleep(0.5)
            
            for post in posts['items']:
                try:            
                    link = 'http://vk.com/{0}?w=wall-{1}_{2}'.format(screen_name, group_id, post['id'])
                    try:
                        comm = post['comments']['count']
                    except:
                        comm = 0
                    try:
                        like = post['likes']['count']
                    except:
                        like = 0
                    try:
                        repo = post['reposts']['count']
                    except:
                        repo = 0
                    try:
                        picture = post['attachments'][0]['photo']['photo_130']
                    except:
                        picture = None
                        
                    save_into_db("insert into postinfo (group_id, link, like, comm, repo, picture) values ({0}, '{1}', {2}, {3}, {4}, '{5}')".format(group_id, link, like, comm, repo, picture))
                    glob += 1
                except BaseException as ex:
                    print "link error: ", ex
            time.sleep(1)
    
    # update statistics: no changes here :)
    a = datetime.now()
    stat = open(os.getcwd() + '/statistics.txt', 'w')
    stat.write(json.dumps({"totalgroups": "{0}".format(len(group_list)), "totalposts": "{0}".format(glob),
                           "time": "{0}".format(datetime.now() - t), "last_update": "{0}:{1}".format(a.hour, a.minute)}))
    stat.close()
    

if __name__ == "__main__":
    while True:                             
        full_cycle()
