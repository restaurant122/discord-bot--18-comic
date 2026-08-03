from datetime import datetime

import datetime
import discord
import random
from discord.ext import commands
import json
import os    
import asyncio
from aiohttp import web
import requests
import re
from bs4 import BeautifulSoup
import curl_cffi
from curl_cffi.requests import AsyncSession


from threading import Thread
from flask import Flask
import aiohttp
import traceback
import jmcomic

jmcomic.JmModuleConfig.FLAG_API_CLIENT_AUTO_UPDATE_DOMAIN = False

option = jmcomic.create_option_by_str('''
client:
  postman:
    type: requests
''')

client = option.build_jm_client()


async def handle_home(request):
    return web.Response(text="Bot is alive!", status=200)

async def run_web_server():
    app = web.Application()
    app.router.add_get("/", handle_home)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Web server 監聽 Port: {port}")

# ==========================================
# 2. 內部自 Ping 保活機制 (雙保險)
# ==========================================
async def self_ping():
    await asyncio.sleep(10) # 啟動後先等 10 秒
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://discord-bot-18-comic-1.onrender.com")
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url, timeout=10) as resp:
                    print(f"🔄 [Self-Ping] 狀態碼: {resp.status}")
            except Exception as e:
                print(f"⚠️ [Self-Ping] 失敗: {e}")
            await asyncio.sleep(240) # 每 4 分鐘自 Ping 一次


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

owneruser='作者:和泉紗霧'



#bot這個物件底下個事件
@bot.event
#上線
async def on_ready():
    print("online")
    await bot.change_presence(status=discord.Status.online,activity=discord.Game("蘿莉"))
    print(bot.user.name)
    print(bot.user.id)
    print('---------')
    bot.loop.create_task(self_ping())
    global owneruser
    owneruser=f'\n作者:{(bot.get_user(613578839372857383))}'



        
    


#ctx=context上下文,包括所在頻道,發言者,id等
         
@bot.event
async def on_message(msg):
    if msg.author==bot.user:
            return
    if msg.content=="時間":
        time=datetime.datetime.now().time()
        await msg.channel.send(time) 
        return
    #觸發其中一個詞就行

      
    elif msg.content=="ping" :
        await msg.channel.send(f"{bot.latency*1000}ms")
        return

    
    elif "aid-" in msg.content :
            index=msg.content.find("aid-")
            bbb = msg.content[index + 4 : index +14]
            album_id=""
            for i in bbb:
                if i.isdigit():
                    album_id+=i
                else:
                    break    
            m=await msg.reply('修復漫畫連結中...',mention_author=False)   
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
                url=f'https://www.wnacg.com/photos-index-aid-{album_id}.html',
                colour=discord.Color.random()
            )
            ec.add_field(name='番號:', value=album_id, inline=True)
            ec.add_field(name='頁數:', value=page_count, inline=True)
            
            if image:
                # 避免重複拼接 https:
                img_url = image if image.startswith('http') else f'https:{image[2:]}'
                ec.set_image(url=img_url)
            ec.set_footer(
                            text=
                            f'{owneruser}\n作者祝您使用愉快'
                        )
            try:
                await msg.edit(suppress=True)
            except:
                pass
            await msg.reply(embed=ec,mention_author=False)    
            await m.delete()
    
    elif "https://telegra.ph" in msg.content :
            bbb=msg.content
            try:
                rr=requests.get(bbb)
                rr.raise_for_status()
            except:
                await msg.reply('telegram漫畫不能有除了連結以外的字符或空白鍵 或是 連結無效',mention_author=False)
            m=await msg.reply('修復漫畫連結中...',mention_author=False)   
            soup=BeautifulSoup(rr.text, features='lxml')
            title=soup.select('title')[0].text.split('- Page 1 –')[0]
            pages=len(soup.select('img'))
            image=soup.select('img')[0]['src']
            ec = discord.Embed(
                    title=f'{title}',
                    description='點上面標題可直接到網站',
                    url=bbb,
                    colour=discord.Color.random()
                )
            ec.add_field(name='頁數:', value=pages, inline=False)
            ec.set_image(url=image)
            ec.set_footer(
                            text=
                            f'{owneruser}\n作者祝您使用愉快'
                        )
            try:
                await msg.edit(suppress=True)
            except:
                pass
            await msg.reply(embed=ec,mention_author=False)
            await m.delete()


    elif "album/" in msg.content :
        
        index = msg.content.find("album/")
        bbb = msg.content[index + 6 : index + 16]
        album_id = ""
        for i in bbb:
            if i.isdigit():
                album_id += i
            else:
                break
        m=await msg.reply('修復漫畫連結中...',mention_author=False)        
                
        try:
            album = client.get_album_detail(album_id)
        except:
            await msg.reply('無此漫畫 請重新檢查',mention_author=False)
            await m.delete()
            return
    
        chapter_count = len(album)
        is_single = (chapter_count <= 1)
    
        pages_info = None
        desc_info = None
    
        if is_single:
            # 單本/單話：抓取頁數資訊
            if chapter_count > 0:
                first_photo_summary = album[0]
                photo_detail = client.get_photo_detail(first_photo_summary.photo_id)
                pages_info = f"{len(photo_detail)} 頁"
            else:
                pages_info = "未知"
        else:
            # 連載作品：抓取作品簡介 (如果 description 為空則顯示預設字串)
            desc_info = album.description.strip() if (album.description and album.description.strip()) else '無簡介資訊'
    
        # 5. 標籤處理 (最多顯示前 10 個)
        tags = album.tags[:10] if album.tags else []
        tags_str = ', '.join(tags) if tags else '無'
    
        cover_url = jmcomic.JmcomicText.get_album_cover_url(album_id)
        ec = discord.Embed(
                title=album.title,
                description='點上面標題可直接到網站',
                url=f'https://18comic.vip/album/{album_id}/',
                colour=discord.Color.random()
            )
        ec.add_field(name='番號:', value=bbb, inline=True)
        ec.add_field(name='作者:', value=album.author, inline=True)
        ec.add_field(name='是否為單本/單話 :', value=f" {'是 (單本/單話)' if is_single else f'否 (連載/共 {chapter_count} 章)'}", inline=False)
        if is_single:
                ec.add_field(name='總頁數:', value=pages_info, inline=True)
        else:
                ec.add_field(name='作品簡介:', value=desc_info, inline=False)
        ec.add_field(name='作品標籤:', value=tags_str, inline=False)
        ec.set_image(url=cover_url)
        ec.set_footer(
                text=
                f'{owneruser}\n作者祝您使用愉快'
            )
    
        await msg.reply(embed=ec,mention_author=False)
        await m.delete()

    


    
    elif msg.author!=bot.user:
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
        await ctx.send("沒有給參數")
    elif isinstance(error,commands.errors.MissingPermissions):
        await ctx.send("沒有權限")  
    elif isinstance(error,commands.CommandOnCooldown):
        await ctx.send(f'冷卻中啦,{error.retry_after:.2f}秒')
    elif isinstance(error,commands.MaxConcurrencyReached):
        await ctx.send('此命令設有可同時使用次數限制') 
    elif  isinstance(error,commands.errors.CommandNotFound):
            pass          
    else:
        await ctx.send(error)
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
async def help(ctx, help=None):
    tell=r'https://telegra.ph/xxxxxx(xxx通常會為一大串 直接貼上即可)'
    comicc=r'https://18comic.vip/album/1427038/xxxxx(xxx通常會為一大串 直接貼上即可)'

    ec = discord.Embed(title='📋歡迎來到說明書📋',
                                description=f'🔺指令前綴:`.`',
                                colour=discord.Color.random())
    ec.add_field(
        name='主要功能:修復h漫畫連結',
        value=f'```用法是直接貼連結即可 不須前綴和指令 目前支援網站:紳士漫畫,telegram漫畫,禁漫天堂，範例:\nhttps://www.wnacg.com/photos-index-aid-374687.html \n{tell}\n{comicc}```'
        ,inline=False)
    ec.add_field(
        name='指令:``.h``',
        value='```.h空一格加上番號 範例:.h 374687```'
        ,inline=False
    )
    ec.add_field(
            name='指令:``.tel``',
            value=f'```.tel空一格加上整個網址\n範例:\n.tel {tell}```'
            ,inline=False
        )
    ec.set_thumbnail(url=bot.user.avatar.url)
    ec.set_image(url='https://media.discordapp.net/attachments/854736687002943488/891300310461587506/Tw.gif')
    ec.set_footer(
        text=
        f'作者關心您{owneruser}'
    )
    await ctx.send(embed=ec)


async def main():
    await run_web_server()
    token = os.getenv("DISCORD_TOKEN")
    await bot.start(token)


if __name__ == '__main__':

    
    asyncio.run(main())
