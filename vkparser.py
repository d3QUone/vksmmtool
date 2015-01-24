from datetime import datetime
import time
import sqlite3
import requests
import json
import sys
import os


def save_log(text):
    # logging & printing - OK
    text = "{0} | {1}\n".format(datetime.now(), text)
    try:
        f = open("logs.txt", "a")
        f.write(text)
        f.close()
    except:
        f = open("logs.txt", "w")
        f.write(text)
        f.close()
    print text


def getA(group_id, auth_token=None, offset=0, count=100):
    # request interface - OK
    if auth_token:
        url = "https://api.vk.com/method/execute.wall"
        data = {"i": "-{0}".format(group_id),
                "o": offset,
                "c": count,
                "access_token": auth_token
            }
    else:
        url = "https://api.vk.com/method/wall.get"
        data = { "owner_id": "-{0}".format(group_id),
                 "offset": offset,
                 "count": count,
                 "v": "5.27"
                 }
    res = requests.get(url, params = data)
    try:
        rjson = res.json()
        if "response" in rjson.keys():
            return rjson["response"]
        else:
            print rjson["error"]
            return {"code": rjson["error"]["error_code"], "message": rjson["error"]["error_msg"]}
    except Exception as e:
        save_log("Requests error: {0}, raw data: {1}".format(e, res.text))
        return {"items": [], "count": 0}


def get_out_db(statement):
    try:
        conn = sqlite3.connect('base.db')
        c = conn.cursor()
        res = c.execute(statement).fetchall()
        conn.close()
        return res
    except Exception as e:
        save_log("get_out_db error: {0}".format(e))
        return []
    

def save_into_db(statement):
    try:
        conn = sqlite3.connect('base.db')
        c = conn.cursor()
        c.execute(statement)
        conn.commit()
        conn.close()
    except Exception as e:
        save_log("save_into_db error: {0}".format(e))


# SMTH WRONG HERE
def get_unique_groups(sql_request):
    all_groups = []
    append = all_groups.append
    all_groups_raw = get_out_db(sql_request)
    for item in all_groups_raw:
        if item[0] not in all_groups:
            append(item[0])
    print "fetched {0} groups".format(len(all_groups))
    return all_groups


def controller():
    processed_groups = [] 
    append = processed_groups.append
    while True:
        all_groups = get_unique_groups("select group_id from groups order by added desc")
        while len(all_groups) == 0:
            print "len all = 0,", all_groups
            time.sleep(3)
            all_groups = get_unique_groups("select group_id from groups order by added desc")

        try:
            new_id = full_cycle_v2(processed_groups, all_groups)
            if new_id:
                append(new_id)
                print "new_id={0} saved".format(new_id)
            else:
                save_log("ID=None, len processed={0}, len all={1}".format(len(processed_groups), len(all_groups)))
                time.sleep(3)
        except Exception as e:
            save_log("full_cycle: {0}, len processed={1}, len all={2}".format(e, len(processed_groups), len(all_groups)))
            time.sleep(3)
        
        if len(all_groups) == len(processed_groups):
            save_log("\nall groups were parsed! {0} groups total\n".format(len(processed_groups)).upper())
            del processed_groups[:]
        print "--"*25
        

# actually scans only 1 group, save parsed groups 
def full_cycle_v2(processed_groups, all_):
    buf_all_groups = list(all_)
    i = 0
    chosen_id = -1
    while i < len(buf_all_groups): 
        group_id = buf_all_groups[i]
        try:
            if group_id not in processed_groups:
                posts = get_out_db("select count(*) from postinfo where group_id = {0}".format(group_id))[0][0]
                if posts == 0:
                    chosen_id = group_id
                    break
                else:
                    # this group isnt new and was parsed some time ago
                    i += 1
            else:
                # this group is already parsed
                buf_all_groups.pop(i)
        except Exception as e:
            save_log("Allert: data error, {0}. Raw: {1}".format(e, item))
            
    try:          
        if chosen_id == -1:
            group_id = buf_all_groups[0] # -- first group of leftover
        else:
            group_id = chosen_id
    except Exception as e:
        print "choose_id exception: {0}, buf_all_groups: {1}".format(e, buf_all_groups)
        return None
    
    auth_token = None
    ret = getA(group_id, auth_token, 0, 1)
    
    # determine here if token is required
    ret_keys = ret.keys()
    if "count" in ret_keys:
        count = ret["count"]
    elif "code" in ret_keys:
        print "\nrefreshing access_token...\n"
        user_id = get_out_db("select user_id from groups where group_id = {0} order by added desc".format(group_id))[0][0]
        auth_token = get_out_db("select auth_token from userinfo where user_id = {0}".format(user_id))[0][0]
        ret = getA(group_id, auth_token, 0, 1)        
        if "count" in ret.keys():
            count = int(ret["count"])
        else:
            print "\nsorry... error_code={0}, message: {1}".format(ret["code"], ret["message"])
            save_log(ret)
            return group_id
    else:
        return group_id
    print "--OK"
    save_into_db('update groups set is_old = 1 where group_id = {0}'.format(group_id))
    save_into_db('delete from postinfo where group_id = {0}'.format(group_id))
    screen_name = get_out_db('select screen_name from groups where group_id = {0}'.format(group_id))[0][0]
    print "screen_name:", screen_name, ", group_id:", group_id, ", nums to parse:", str(count)

    try:
        req = "https://api.vk.com/method/groups.getById?group_id={0}".format(group_id)
        written_name = requests.get(req).json()["response"][0]["name"]
    except Exception as ex:
        save_log("no written_name: {0}".format(ex))
        written_name = screen_name
    print "name:", written_name

    # UPDATE GROUP-INFO IN THE STATS
    try:
        f = open(os.getcwd() + '/statistics.txt', 'r')
        data = json.loads(f.read())
        f.close()
    except:
        data = {}
    if len(written_name) > 35:
        data["name"] = written_name[:32] + "..."
    else:
        data["name"] = written_name
    data["count"] = count
    data["group_id"] = group_id
    data["totalgroups"] = len(all_)
    
    f = open(os.getcwd() + '/statistics.txt', 'w')
    f.write(json.dumps(data))
    f.close()

    # LOAD AND PROCESS VK-POSTS
    offset = count//100 + 1
    for i in range(0, offset):
        posts = getA(group_id, auth_token, i*100, 100)
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
                    picture = None
                    if 'attachments' in post.keys():
                        a_type = post['attachments'][0]['type']
                        if a_type in ['photo', 'video']:
                            picture = post['attachments'][0][a_type]['photo_130']
                except Exception as ex:
                    picture = None
                save_into_db("insert into postinfo (group_id, link, like, comm, repo, picture) values ({0}, '{1}', {2}, {3}, {4}, '{5}')".format(group_id, link, like, comm, repo, picture))
            except BaseException as ex:
                save_log("link error: {0}, full post: {1}, full response: {2}".format(ex, post, posts))
                print "link error: ", ex, "full post: ", post
        # UPDATE POSTs-INFO IN THE STATS
        f = open(os.getcwd() + '/statistics.txt', 'r')
        data = json.loads(f.read())
        f.close()
        data["count"] -= len(posts["items"])
        if data["count"] < 0:
            data["count"] = 0
        f = open(os.getcwd() + '/statistics.txt', 'w')
        f.write(json.dumps(data))
        f.close()
        
        time.sleep(0.05)
    return group_id


ver = "2c"
if __name__ == "__main__":
    save_log("vkparser v={0} is running!".format(ver))
    print "--"*25
    controller()
