from datetime import datetime

import datetime
import discord
import random
from discord.ext import commands
import json
with open("setting.json","r",encoding="utf8") as file:
    data=json.load(file)
import os    
import asyncio

import requests
import re
from bs4 import BeautifulSoup
import curl_cffi






intents=discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # 如果有用到成員資料
intents.messages = True
intents.voice_states = True
intents.reactions=True
intents.presences = True

#建置實體機器人
bot=commands.Bot(command_prefix=".",intents=intents)
bot.remove_command('help')
#符號那邊可以是空的,如果是空的會達成跟onmessage一樣效果


from threading import Thread
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    # 只要 UptimeRobot 或浏览器访问这个网址，就会收到这个响应
    return "Bot is alive!"

def run_web_server():
    # Render 会自动提供 PORT 环境变量，默认使用 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    # 开一个新的线程去跑 Flask，避免阻塞主程序
    t = Thread(target=run_web_server)
    t.daemon = True  # 设置为守护线程，Bot 停止时网页服务也会跟着停止
    t.start()


#bot這個物件底下個事件
@bot.event
#上線
async def on_ready():
    print("online")
    await bot.change_presence(status=discord.Status.online,activity=discord.Game("蘿莉"))
    print(bot.user.name)
    print(bot.user.id)
    print('---------')



        
    


#ctx=context上下文,包括所在頻道,發言者,id等
         
@bot.event
async def on_message(msg):

    if msg.content=="時間":
        time=datetime.datetime.now().time()
        await msg.channel.send(time) 
        return
    #觸發其中一個詞就行
    keyword=["apple","hi","abc","key"]
    if msg.content in keyword and msg.author != bot.user:
        await msg.channel.send("hi") 
        return
      
    if msg.content=="ping" and msg.author!=bot.user:
        await msg.channel.send(f"{bot.latency*1000}ms")
        return
    
    if "index-aid-" in msg.content and msg.author!=bot.user:
        index=msg.content.find("index-aid-")
        bbb = msg.content[index + 10 : index +20]
        album_id=""
        for i in bbb:
            if i.isdigit():
                album_id+=i
            else:
                break    
        try:
            res = requests.get(f'https://www.wn07.cfd/photos-index-aid-{album_id}.html', timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, features='lxml')
        except Exception:
            await msg.reply('搜尋不到該番號或網站無法連線。',mention_author=False)
            return  

        # 安全地解析元素
        imgs = soup.select('img')
        if len(imgs) < 6:
            await msg.reply('頁面解析失敗（圖片數量不足或番號不存在）。',mention_author=False)
            return

        title = imgs[2].get('alt', '無標題')
        image = imgs[2].get('src', '')

        # 解析頁數
        labels = soup.select('label')
        page_count = '未知'
        if len(labels) > 1 and '：' in labels[1].text:
            page_count = labels[1].text.split('：')[1].split('P')[0]

        # 建立 Embed
        ec = discord.Embed(
            title=title,
            description='點上面標題可直接到網站',
            url=f'https://www.wnacg.org/photos-index-aid-{bbb}.html',
            colour=discord.Color.random()
        )
        ec.add_field(name='番號:', value=bbb, inline=True)
        ec.add_field(name='頁數:', value=page_count, inline=True)
        
        if image:
            # 避免重複拼接 https:
            img_url = image if image.startswith('http') else f'https:{image[2:]}'
            ec.set_image(url=img_url)
        try:
            await msg.edit(suppress=True)
        except:
            pass
        await msg.reply(embed=ec,mention_author=False)    


    if "album/" in msg.content and msg.author!=bot.user:
        index=msg.content.find("album/")
        bbb = msg.content[index + 6 : index +16]
        album_id=""
        for i in bbb:
            if i.isdigit():
                album_id+=i
            else:
                break    
        url = f"https://18comic.vip/album/{album_id}/"
    
        i=1
        # =====================
        # 發送請求 (模擬真實 Chrome 120 的 TLS 指紋)
        # =====================
        # impersonate="chrome120" 可以完美模擬 Chrome 的底層網絡指紋，輕鬆過 Cloudflare
        # 加上 verify=False 繞過憑證檢查
        while(i!=0):
            response = curl_cffi.requests.get(url, impersonate="chrome120", verify=False)
    
            if response.status_code != 200:
                print(f"請求失敗，狀態碼：{response.status_code}")
                i+=1
                continue
            if i==10:
                await msg.channel.send("錯誤")
                return
            i=0
    
    
        # =====================
        # BeautifulSoup 解析
        # =====================
        soup = BeautifulSoup(response.text, "html.parser")
    
        # 1. 標題
        title = None
        title_tag = soup.find("h1", id="book-name")
        if title_tag:
            title = title_tag.text.strip()
    
        # 2. 封面
        cover = f"https://cdn-msp3.18comic.vip/media/albums/{album_id}.jpg"
    
        # 3. 頁數
        pages = None
        page_element = soup.find(
            lambda tag: tag.name in ["div", "span", "p", "h2"]
            and "頁數" in tag.text
            and tag.find(["div", "span", "p", "h2"]) is None
        )
    
        if page_element:
            match = re.search(r"\d+", page_element.text)
            if match:
                pages = match.group()
    
        # 4. 日期
        date = None
        text = soup.get_text("\n", strip=True)
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if date_match:
            date = date_match.group()
    
        # 5. 標籤 (Tags)
        tags = []
        tag_container = soup.find("span", {"itemprop": "genre", "data-type": "tags"})
        if tag_container:
            for a in tag_container.find_all("a"):
                tag_name = a.text.strip()
                if tag_name:
                    tags.append(tag_name)
        comic = {
            "ID": album_id,
            "標題": title,
            "頁數": pages,
            "日期": date,
            "標籤": tags,
            "封面": cover,
        }
    
    
        # 建立 Embed
        ec = discord.Embed(
            title=f'{title}',
            description='點上面標題可直接到網站',
            url=f"https://18comic.vip/album/{album_id}/",
            colour=discord.Color.random()
        )
        ec.add_field(name='番號:', value=bbb, inline=False)
        ec.add_field(name='頁數:', value=pages, inline=False)
        str123=""
        for i in tags[:10]:
            str123+=f"{i} ,"
        ec.add_field(name='標籤:', value=str123, inline=False)
        ec.add_field(name='上架日期:', value=date, inline=False)
        ec.set_image(url=cover)
        
    
        await msg.reply(embed=ec,mention_author=False)


    
    if msg.author!=bot.user:
        if not msg.guild:
            embed=discord.Embed(title=f"有人傳送訊息給{bot.user.name},以下為信件內容",colour=discord.Color.random())
            embed.add_field(name="用戶",value=msg.author)
            embed.add_field(name="內容",value=msg.content)
            await bot.get_guild(850599773354328095).get_channel(850625850767573012).send(embed=embed)


    await bot.process_commands(msg)   
    #防止on message跟command衝突    

 



#取得此伺服器擁有者id
@bot.command()
async def si(ctx):
    guild=bot.get_guild(850599773354328095)   
    owner=guild.owner_id
    await ctx.send(owner) 


# 僅管理者使用
# @commands.has_permissions(administrator=True)    
            

@bot.event
async def on_command_error(ctx,error):
    if hasattr(ctx.command,"on_error"):
        return
    if isinstance(error,commands.errors.MissingRequiredArgument):
        await ctx.send("你他媽沒有給我參數")
    elif  isinstance(error,commands.errors.CommandNotFound):
        await ctx.send("沒有這指令唷~") 
    elif isinstance(error,commands.errors.MissingPermissions):
        await ctx.send("沒有權限啦廢物")  
    elif isinstance(error,commands.CommandOnCooldown):
        await ctx.send(f'冷卻中啦,等個{error.retry_after:.2f}秒會死喔')
    elif isinstance(error,commands.MaxConcurrencyReached):
        await ctx.send('此命令設有可同時使用次數限制')           
    else:
        raise error    




      





@bot.command()
async def sev(ctx):
    em=discord.Embed(title="伺服器狀態",color=discord.Color.random())
    em.add_field(name="伺服器名稱",value=ctx.guild.name)
    em.add_field(name="伺服器創建時間", value=ctx.guild.created_at.strftime("%Y年%m月%d日"),inline=False)
    em.add_field(name="成員數",value=len(ctx.guild.members),inline=True)
    em.add_field(name="頻道數量",value=len(ctx.guild.channels),inline=True)
    em.add_field(name="身分組數量",value=len(ctx.guild.roles),inline=True)  
    em.set_thumbnail(url=ctx.guild.icon_url)
    em.set_footer(text="色情查詢系統")
    await ctx.send(embed=em)
    ccc=[]
    for namea in ctx.guild.roles:
        ccc.append(namea.name)   
    asa=discord.Embed(title="身分組",description=ccc,color=discord.Color.random())
    await ctx.send(embed=asa)



@bot.command()
@commands.is_owner()
async def players(ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed()
        embed.set_author(name=member, icon_url=member.avatar_url)
        embed.set_thumbnail(url=member.avatar_url)
        embed.add_field(name=":computer:帳號創建時間", value=member.created_at.strftime("%Y年%m月%d日"), inline=True)            
        embed.add_field(name=":calling:加入伺服器時間", value=member.joined_at.strftime("%Y年%m月%d日"), inline=True)            
        since = member.premium_since
        embed.add_field(name=":gem:加成伺服器時間",value=since.strftime("%Y年%m月%d日") if since else "無加成", inline=True)               
        embed.add_field(name="是否為bot", value="是"if member.bot else "否", inline=True)
        embed.add_field(name="目前狀態", value=member.status, inline=True) 
        embed.add_field(name="最高權限身分組", value=member.top_role.mention)   
        embed.set_footer(text='色情查詢系統')
        await ctx.send(embed=embed)



@bot.command()
@commands.is_owner()
async def www(ctx,member:discord.Member,*,mes):  
    await ctx.message.delete()  
    await member.send(mes)
    c=await ctx.send("訊息已發送")
    await asyncio.sleep(5)
    await c.delete()   



@bot.command()
async def n(ctx,bbb=None):
    if bbb==None:
        await ctx.send('你沒有給我番號,我將隨機生成')
        while True:
            bbb=random.randint(100000,999999)
            print(bbb)   
            try:
                req=requests.get(f'https://nhentai.net/g/{bbb}/')
                soup=BeautifulSoup(req.text,features='lxml')
                imgs=soup.select('img')[2]
                app=imgs['src']
                title=soup.select('span')
                break
            except:
                continue
    else:
        try:
                req=requests.get(f'https://nhentai.net/g/{bbb}/')
                soup=BeautifulSoup(req.text,features='lxml')
                imgs=soup.select('img')[2]
                app=imgs['src']
                title=soup.select('span')
        except:
                await ctx.send('搜尋失敗')        
    title3=[]
    asa=[]
    asa2=[]
    lan=[]
    for title2 in title:
        try:
            if title2['class']==['pretty']:
                title3.append(str(title2).split('>')[1].split('<')[0])
                break
        except:
            continue
    for title2 in title:
        try:
            if title2['class']==['name']:
                asa.append(title2)
                continue
        except:
            continue
    for title2 in title:
        try:
            if title2['class']==['after']:
                lan.append(str(title2).split('[')[1].split(']')[0])
                break
        except:
            lan.append('None')       
    try:
        asa2.append(str(asa[-1]).split('>')[1].split('<')[0])
    except:
        await ctx.send('搜不到')
        return
    ec=discord.Embed(title=f':link:{title3[0]}',description='點上面標題可直接到網站',url=f'https://nhentai.net/g/{bbb}/',colour=discord.Color.random())
    ec.add_field(name='ℹ️番號:',value=bbb)
    ec.add_field(name=':speech_balloon:語言:',value=lan[0])
    ec.add_field(name=':book:頁數:',value=asa2[0])
    ec.add_field(name='封面圖',value='⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️',inline=False)
    ec.set_image(url=app)
    ec.set_thumbnail(url='https://i.imgur.com/uLAimaY.png')
    ec.set_footer(text='語言僅供參考,未必準確,None表示沒抓到')
    await ctx.send(embed=ec)     



@bot.command()
async def h(ctx, bbb=None):
    if bbb is None:
        await ctx.send('沒有給我番號')
        
    # 抓取指定番號頁面
    try:
        res = requests.get(f'https://www.wn07.cfd/photos-index-aid-{bbb}.html', timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, features='lxml')
    except Exception:
        await ctx.send('搜尋不到該番號或網站無法連線。')
        return  

    # 安全地解析元素
    imgs = soup.select('img')
    if len(imgs) < 6:
        await ctx.send('頁面解析失敗（圖片數量不足或番號不存在）。')
        return

    title = imgs[2].get('alt', '無標題')
    image = imgs[2].get('src', '')

    # 解析頁數
    labels = soup.select('label')
    page_count = '未知'
    if len(labels) > 1 and '：' in labels[1].text:
        page_count = labels[1].text.split('：')[1].split('P')[0]

    # 建立 Embed
    ec = discord.Embed(
        title=title,
        description='點上面標題可直接到網站',
        url=f'https://www.wnacg.org/photos-index-aid-{bbb}.html',
        colour=discord.Color.random()
    )
    ec.add_field(name='番號:', value=bbb, inline=True)
    ec.add_field(name='頁數:', value=page_count, inline=True)
    
    if image:
        # 避免重複拼接 https:
        img_url = image if image.startswith('http') else f'https:{image[2:]}'
        ec.set_image(url=img_url)

    await ctx.send(embed=ec)

@bot.command()
async def w(ctx, bbb=None):
    album_id = bbb
    url = f"https://18comic.vip/album/{album_id}/"

    i=1
    # =====================
    # 發送請求 (模擬真實 Chrome 120 的 TLS 指紋)
    # =====================
    # impersonate="chrome120" 可以完美模擬 Chrome 的底層網絡指紋，輕鬆過 Cloudflare
    # 加上 verify=False 繞過憑證檢查
    while(i!=0):
        response = curl_cffi.requests.get(url, impersonate="chrome120", verify=False)

        if response.status_code != 200:
            print(f"請求失敗，狀態碼：{response.status_code}")
            i+=1
            continue
        if i==10:
            ctx.send("錯誤")
            return
        i=0


    # =====================
    # BeautifulSoup 解析
    # =====================
    soup = BeautifulSoup(response.text, "html.parser")

    # 1. 標題
    title = None
    title_tag = soup.find("h1", id="book-name")
    if title_tag:
        title = title_tag.text.strip()

    # 2. 封面
    cover = f"https://cdn-msp3.18comic.vip/media/albums/{album_id}.jpg"

    # 3. 頁數
    pages = None
    page_element = soup.find(
        lambda tag: tag.name in ["div", "span", "p", "h2"]
        and "頁數" in tag.text
        and tag.find(["div", "span", "p", "h2"]) is None
    )

    if page_element:
        match = re.search(r"\d+", page_element.text)
        if match:
            pages = match.group()

    # 4. 日期
    date = None
    text = soup.get_text("\n", strip=True)
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if date_match:
        date = date_match.group()

    # 5. 標籤 (Tags)
    tags = []
    tag_container = soup.find("span", {"itemprop": "genre", "data-type": "tags"})
    if tag_container:
        for a in tag_container.find_all("a"):
            tag_name = a.text.strip()
            if tag_name:
                tags.append(tag_name)
    comic = {
        "ID": album_id,
        "標題": title,
        "頁數": pages,
        "日期": date,
        "標籤": tags,
        "封面": cover,
    }


    # 建立 Embed
    ec = discord.Embed(
        title=f'{title}',
        description='點上面標題可直接到網站',
        url=f"https://18comic.vip/album/{album_id}/",
        colour=discord.Color.random()
    )
    ec.add_field(name='番號:', value=bbb, inline=False)
    ec.add_field(name='頁數:', value=pages, inline=False)
    str123=""
    for i in tags[:10]:
        str123+=f"{i} ,"
    ec.add_field(name='標籤:', value=str123, inline=False)
    ec.add_field(name='上架日期:', value=date, inline=False)
    ec.set_image(url=cover)
    

    await ctx.send(embed=ec)











# bot.add_cog(Music(bot))


if __name__ == '__main__':
    # 先启动 HTTP Web 服务器
    keep_alive()
    
    # 再启动 Discord Bot
    token = os.getenv("DISCORD_TOKEN")
    bot.run(token)

