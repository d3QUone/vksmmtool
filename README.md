<b>VKSMM</b> is a cool service to get the most popular content from your "vk.com" communities

[![Build Status](https://travis-ci.org/d3QUone/vksmmtool.svg?branch=master)](https://travis-ci.org/d3QUone/vksmmtool)

<hr>
<b>How to run:</b>

1) Setup all required modules on your server 

2) Create project folders:

\vksmmtool <br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\templates <br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\static <br>

Don't forget to add graphic files to "\static" folder:<br>
```
"none.png", "Comment-Icon-copy.png", "Comment-Icon-sort.png", "Like-Icon-copy.png"
"Like-Icon-sort.png", "Repost-Icon-copy.png", "Repost-Icon-sort.png"
```

3) Fill them and setup DB via bash from \vksmmtool-folder:

```bash
python

>>> import server
>>> server.init_db()
```

4) Run parser in a screen

<code>screen python vkparser.py</code>

5) Setup NGNIX-server and Gunicorn, following  <a href="https://realpython.com/blog/python/kickstarting-flask-on-ubuntu-setup-and-deployment/">this article</a>, restart it and run app from the project folder, e.g:

```bash
sudo /etc/init.d/nginx restart
cd user/vksmmmtool
gunicorn -w 2 -b localhost:8000 server:app --daemon
```
