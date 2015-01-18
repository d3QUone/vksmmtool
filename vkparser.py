from datetime import datetime
import time
import sqlite3
import requests
import json
import sys
import os


# logging - OK
def save_log(text):
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


# request interface - OK
def getA(group_id, auth_token=None, offset=0, count=100):
    url = "https://api.vk.com/method/wall.get"
    data = { "owner_id": "-{0}".format(group_id),
             "offset": offset,
             "count": count,
             "v": "5.27"
             }
    if auth_token:
        data["access_token"] = auth_token
    res = requests.get(url, params = data)
    try:
        rjson = res.json()
        if "response" in rjson.keys():
            return rjson["response"]
        else:
            #print "fuck: {0}".format(rjson["error"])
            return {"code": rjson["error"]["error_code"], "message": rjson["error"]["error_msg"]}
    except Exception as e:
        save_log("Requests error: {0}".format(e))
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


def get_unique_groups(params):
    # params: "select added, group_id from groups"
    all_groups_raw = get_out_db(params)
    all_groups = []
    append = all_groups.append
    for item in all_groups_raw:
        if item not in all_groups:
            append(item)
    all_groups.sort()
    return all_groups


def controller():
    processed_groups = [] 
    append = processed_groups.append
    while True:
        t = datetime.now()
        all_groups = get_unique_groups("select added, group_id from groups")
        try:
            new_id = full_cycle_v2(processed_groups, all_groups)
            print "new_id", new_id
            append(new_id)
        except Exception as e:
            save_log("full_cycle error: {0}".format(e))
            print "full_cycle error: {0}".format(e)
        if len(all_groups) == len(processed_groups):
            print "all groups were updated!".upper()
            del processed_groups[:]
            
        # update stats
        a = datetime.now()
        a_h = a.hour
        a_m = a.minute
        if a_h < 10 and a_m < 10:
            last_update = "0{0}:0{1}".format(a_h, a_m)
        elif a_h >= 10 and a_m < 10:
            last_update = "{0}:0{1}".format(a_h, a_m)
        elif a_h < 10 and a_m >= 10:
            last_update = "0{0}:{1}".format(a_h, a_m)
        else:
            last_update = "{0}:{1}".format(a_h, a_m)
        dt = "{0}".format(a - t)
        dt = dt.split(".")[0]
        stat = open(os.getcwd() + '/statistics.txt', 'w')
        stat.write(json.dumps({"totalgroups": "{0}".format(len(all_groups)), "totalposts": 0, "time": dt, "last_update": last_update}))
        stat.close()

        print "--"*25
        print "new cycle:\n"
    

# actually scans only 1 group, save parsed groups 
def full_cycle_v2(processed_groups, all_):
    all_groups = all_
    i = 0
    chosen_id = -1
    while i < len(all_groups):
        item = all_groups[i]
        try:
            group_id = item[1] # if error (what error?) -- alert and move forward
            if group_id not in processed_groups:
                posts = get_out_db("select link from postinfo where group_id = {0}".format(group_id))
                #print "group_id={0}, {1} posts in base".format(group_id, len(posts))
                if len(posts) == 0: # group is new or closed, anyway - we start with this group
                    chosen_id = group_id
                    break
                else: # this group isnt new and isnt parsed
                    i += 1
            else: # this group is already parsed
                all_groups.pop(i)
                
        except Exception as e:
            print "Allert: data error, {0}. Raw: {1}".format(e, item)

    # process chosen id           
    if chosen_id != -1:
        group_id = chosen_id
    else:
        group_id = all_groups[0][1] # -- first group of leftover
    print "group_id =", group_id
    auth_token = None
    ret = getA(group_id, auth_token, 0, 1)

    # determine here if token is required
    ret_keys = ret.keys()
    if "count" in ret_keys:
        count = ret["count"]
    elif "code" in ret_keys:
        error_code = ret["code"]
        print "error_code: {0}, message: {1}".format(error_code, ret["message"])

        user_id = get_out_db("select user_id from groups where group_id = {0} order by added desc".format(group_id))[0][0]
        auth_token = get_out_db("select auth_token from userinfo where user_id = {0}".format(user_id))
        ret = getA(group_id, auth_token, 0, 1)

        # get count or error
        print "new response: {0}".format(ret)
        if "count" in ret.keys():
            count = ret["count"]
        else:
            #print "sorry: {0}".format(ret)
            return group_id
    else:
        return group_id

    save_into_db('delete from postinfo where group_id = {0}'.format(group_id))
    screen_name = get_out_db('select screen_name from groups where group_id = {0}'.format(group_id))[0][0]
    print "screen_name:", screen_name, ", group_id:", group_id, ", nums to parse:", str(count)
    
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
                    picture = post['attachments'][0]['photo']['photo_130']
                except:
                    picture = None
                save_into_db("insert into postinfo (group_id, link, like, comm, repo, picture) values ({0}, '{1}', {2}, {3}, {4}, '{5}')".format(group_id, link, like, comm, repo, picture))
            except BaseException as ex:
                save_log("link error: {0}".format(ex))
                print "link error: ", ex
        time.sleep(0.35)
    return group_id


if __name__ == "__main__":
    controller()
