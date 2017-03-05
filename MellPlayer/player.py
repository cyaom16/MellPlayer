#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
MellPlayer Player

Created on 2017-02-20
@author: Mellcap
'''

import os
import time
import threading

from utils.mpv import MPV
from api import Netease
from directory import BASE_DIRECTORY

PLAYLIST_MAX = 50
PLAYLIST_FILE = os.path.join(BASE_DIRECTORY, 'playlist.m3u')
NeteaseApi = Netease()


class Player(MPV):

    def __init__(self, *extra_mpv_flags, log_handler=None, start_event_thread=True, **extra_mpv_opts):
        super(Player, self).__init__(*extra_mpv_flags, log_handler=log_handler, start_event_thread=start_event_thread, **extra_mpv_opts)
        self.category = None
        self.category_playlist_ids = None
        self.category_playlist_index = 0
        self.playlist_ids = None
        self.playlist_index = 0
        self.playlist_detail = None
        self.song_info = ''
        self.is_quit = False

    # ===========================
    # Player Controller
    # ===========================

    def start_or_pause(self):
        self.pause = not self.pause

    def switch_song(self, action='next'):
        '''
        action: next/prev
        '''
        if action == 'next':
            self.playlist_next()
        elif action == 'prev':
            self.playlist_prev()

    def next_song(self):
        # self.playlist_next()
        playlist_ids = self.playlist_ids
        if playlist_ids:
            self.playlist_index += 1
            if self.playlist_index >= len(playlist_ids):
                self.playlist_index = 0
            self.run_player()

    def prev_song(self):
        # self.playlist_prev()
        playlist_ids = self.playlist_ids
        if playlist_ids:
            self.playlist_index -= 1
            if self.playlist_index < 0:
                self.playlist_index = len(self.playlist_ids) - 1
            self.run_player()

    def switch_playlist(self):
        '''
        action: next/prev
        '''
        if action == 'next':
            self.next_playlist()
        elif action == 'prev':
            self.prev_playlist()

    def next_playlist(self):
        category_playlist_ids = self.category_playlist_ids
        if category_playlist_ids:
            self.category_playlist_index += 1
            if self.category_playlist_index >= len(self.category_playlist_ids):
                self.category_playlist_index = 0
            self.run_playlist()

    def prev_playlist(self):
        category_playlist_ids = self.category_playlist_ids
        if category_playlist_ids:
            self.category_playlist_index -= 1
            if self.category_playlist_index < 0:
                self.category_playlist_index = len(self.category_playlist_ids) - 1
            self.run_playlist()
    
    def switch_category(self, new_category):
        self.category = new_category
        self.get_category_playlist_ids()
        self.run_playlist()
    
    # ===========================
    # Play Info
    # ===========================
    
    def get_category_playlist_ids(self):
        '''
        获取该类别-歌单id列表
        '''
        category = self.category or '全部'
        # initial category_playlist_index
        self.category_playlist_index = 0
        # get data
        data = NeteaseApi.category_playlists(category=category)
        category_playlist_ids = NeteaseApi.parse_info(data=data, parse_type='category_playlists')
        self.category_playlist_ids = tuple(category_playlist_ids)
    
    def get_playlist(self):
        '''
        获取该歌单-歌曲id列表
        '''
        playlist_id = self.category_playlist_ids[self.category_playlist_index]
        data = NeteaseApi.playlist_detail(playlist_id)
        playlist_ids, playlist_detail = NeteaseApi.parse_info(data=data, parse_type='playlist_detail')
        self.playlist_ids = playlist_ids
        self.playlist_detail = playlist_detail
        self.update_playlist_url()

    def update_playlist_url(self):
        '''
        旧的mp3_url有很多无法播放，采用新的接口
        新接口mp3_url已知问题：有时间戳，经过一段时间失效
        '''
        song_ids = self.playlist_ids
        data = NeteaseApi.song_detail_new(song_ids)
        song_details = NeteaseApi.parse_info(data=data, parse_type='song_detail_new')
        for song_id in self.playlist_detail:
            song_detail = song_details.get(song_id, None)
            if not song_detail:
                continue
            song_info = {
                'song_url': song_detail.get('song_url', None),
                'song_br': song_detail.get('song_br', None)
            }
            self.playlist_detail[song_id].update(song_info)

    def update_song_info(self):
        '''
        更新歌曲信息：歌名 & 歌手名
        '''
        if self.playlist_ids and self.playlist_detail:
            play_detail = self.playlist_detail.get(self.playlist_ids[self.playlist_index], None)
            if play_detail:
                self.song_info = [play_detail.get('song_name', ''), play_detail.get('song_artists', '')]

    def get_play_info(self):
        '''
        待作废接口
        '''
        self.update_song_info()
        return self.song_info


    def run_playlist(self):
        '''
        启动播放列表
        '''
        # initial playlist_index
        self.playlist_index = 0
        self.get_playlist()
        self.run_player()
            
    def run_player(self):
        '''
        启动播放器
        '''
        if self.playlist_detail and self.playlist_ids:
            song_info = self.playlist_detail.get(self.playlist_ids[self.playlist_index], None)
            if not song_info:
                # @TODO add logger
                pass
            song_url = song_info.get('song_url', None)
            if not song_url:
                # @TODO add logger
                pass
            self.play(song_url)


    # ===========================
    # Volume Controller
    # ===========================
    
    def reduce_volume(self, step=10):
        '''
        减小音量
        '''
        volume = max(self.volume - step, 0)
        self.volume = volume

    def increase_volume(self, step=10):
        '''
        增加音量
        '''
        volume = min(self.volume + step, 100)
        self.volume = volume

    def mute_volume(self):
        '''
        静音
        '''
        self.mute = not self.mute


    # ===========================
    # Playlist 
    # ===========================
    # ***Have some bugs
    
    def init_playlist(self):
        '''
        playlist会发生闪退问题，暂时自己控制播放列表
        '''
        if os.path.exists(PLAYLIST_FILE):
            self.loadlist(PLAYLIST_FILE)

    def loop_playlist(self):
        '''
        循环播放
        '''
        self._set_property('loop', True)
        
    def save_playlist(self):
        '''
        保存播放列表为m3u格式
        '''
        playlist = []
        m3u_title = '#EXTM3U\n'
        playlist.append(m3u_title)
        for song in self.playlist_detail:
            song_detail = '#EXTINF:,%s\n%s\n' % (song['song_id'], song['song_url'])
            playlist.append(song_detail)
        with open(PLAYLIST_FILE, 'w') as f:
            for line in playlist:
                f.write(line)
        return True


# ===========================
# Instance
# ===========================

def mell_logger(loglevel, component, message):
    if loglevel == 'error':
        # print('[{}] {}: {}\r'.format(loglevel, component, message))
        play_next_song()
        
mell_player = Player(log_handler=mell_logger, ytdl=True)

def play_next_song():
    mell_player.next_song()
