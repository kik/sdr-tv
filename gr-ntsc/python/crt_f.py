#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2014 <+YOU OR YOUR COMPANY+>.
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

import numpy
from gnuradio import gr
from gnuradio.wxgui import scope_window
from gnuradio.wxgui import common
from gnuradio import gr, filter
from gnuradio import blocks
from gnuradio import analog
from gnuradio import wxgui
from gnuradio.wxgui.pubsub import pubsub
from gnuradio.wxgui.constants import *
from gnuradio.wxgui.scopesink_gl import *
from gnuradio.wxgui import plotter
import math
from OpenGL import GL

CHANNEL_COLOR_SPECS = (
	(0.3, 0.3, 1.0),
	(0.0, 0.8, 0.0),
	(1.0, 0.0, 0.0),
	(0.8, 0.0, 0.8),
        (0.7, 0.7, 0.0),
        (0.15, 0.90, 0.98),

)

SAMPLES_KEY = 'samples'
COLOR_SPEC_KEY = 'color_spec'
MARKERY_KEY = 'marker'
TRIG_OFF_KEY = 'trig_off'

class my_plotter(plotter.channel_plotter):
	def __init__(self, parent):
		"""
		Create a new channel plotter.
		"""
                plotter.channel_plotter.__init__(self, parent)

	def _init_channel_plotter(self):
		"""
		Run gl initialization tasks.
		"""
		GL.glEnableClientState(GL.GL_VERTEX_ARRAY)

	def _draw_waveforms(self):
		"""
		Draw the waveforms for each channel.
		Scale the waveform data to the grid using gl matrix operations.
		"""
		GL.glEnableClientState(GL.GL_COLOR_ARRAY)
		#use scissor to prevent drawing outside grid
		GL.glEnable(GL.GL_SCISSOR_TEST)
		GL.glScissor(
			self.padding_left+1,
			self.padding_bottom+1,
			self.width-self.padding_left-self.padding_right-1,
			self.height-self.padding_top-self.padding_bottom-1,
		)
		for channel in reversed(sorted(self._channels.keys())):
			samples = self._channels[channel][SAMPLES_KEY]
			num_samps = len(samples)
			if not num_samps: continue
			#use opengl to scale the waveform
			GL.glPushMatrix()
			GL.glTranslatef(self.padding_left, self.padding_top, 0)
			GL.glScalef(
				(self.width-self.padding_left-self.padding_right),
				(self.height-self.padding_top-self.padding_bottom),
				1,
			)
			GL.glTranslatef(0, 1, 0)
			if isinstance(samples, tuple):
				x_scale, x_trans = 1.0/(self.x_max-self.x_min), -self.x_min
                                xy = (samples[0], samples[1])
                                z = samples[2]
				points = zip(*xy)
                                colors = zip(z, z, z)
			else:
				x_scale, x_trans = 1.0/(num_samps-1), -self._channels[channel][TRIG_OFF_KEY]
				points = zip(numpy.arange(0, num_samps), samples)
			GL.glScalef(x_scale, -1.0/(self.y_max-self.y_min), 1)
			GL.glTranslatef(x_trans, -self.y_min, 0)
			#draw the points/lines
			#GL.glColor3f(*self._channels[channel][COLOR_SPEC_KEY])
                        GL.glColorPointerf(colors)
			marker = self._channels[channel][MARKERY_KEY]
			if marker is None:
				GL.glVertexPointerf(points)
				GL.glDrawArrays(GL.GL_LINE_STRIP, 0, len(points))
			elif isinstance(marker, (int, float)) and marker > 0:
				GL.glPointSize(marker)
				GL.glVertexPointerf(points)
				GL.glDrawArrays(GL.GL_POINTS, 0, len(points))
			GL.glPopMatrix()
		GL.glDisable(GL.GL_SCISSOR_TEST)
		GL.glDisableClientState(GL.GL_COLOR_ARRAY)

	def _draw_point_label(self):
            return


class my_scope_window(scope_window.scope_window):
	def __init__(
		self,
		parent,
		controller,
		size,
		title,
		frame_rate,
		num_inputs,
		sample_rate_key,
		t_scale,
		v_scale,
		v_offset,
		xy_mode,
		ac_couple_key,
		trigger_level_key,
		trigger_mode_key,
		trigger_slope_key,
		trigger_channel_key,
		decimation_key,
		msg_key,
                use_persistence,
                persist_alpha,
		trig_mode,
		y_axis_label,
	):
		pubsub.__init__(self)
		#check num inputs
		assert num_inputs <= len(CHANNEL_COLOR_SPECS)
		#setup
		self.sampleses = None
		self.num_inputs = num_inputs
		autorange = not v_scale
		self.autorange_ts = 0
		v_scale = v_scale or 1
		self.frame_rate_ts = 0
		#proxy the keys
		self.proxy(MSG_KEY, controller, msg_key)
		self.proxy(SAMPLE_RATE_KEY, controller, sample_rate_key)
		self.proxy(TRIGGER_LEVEL_KEY, controller, trigger_level_key)
		self.proxy(TRIGGER_MODE_KEY, controller, trigger_mode_key)
		self.proxy(TRIGGER_SLOPE_KEY, controller, trigger_slope_key)
		self.proxy(TRIGGER_CHANNEL_KEY, controller, trigger_channel_key)
		self.proxy(DECIMATION_KEY, controller, decimation_key)
		#initialize values
		self[RUNNING_KEY] = True
		self[XY_MARKER_KEY] = 2.0
		self[CHANNEL_OPTIONS_KEY] = 0
		self[XY_MODE_KEY] = xy_mode
		self[X_CHANNEL_KEY] = 0
		self[Y_CHANNEL_KEY] = 1
		self[AUTORANGE_KEY] = autorange
		self[T_PER_DIV_KEY] = t_scale
		self[X_PER_DIV_KEY] = v_scale
		self[Y_PER_DIV_KEY] = v_scale
		self[T_OFF_KEY] = 0
		self[X_OFF_KEY] = v_offset
		self[Y_OFF_KEY] = v_offset
		self[T_DIVS_KEY] = 8
		self[X_DIVS_KEY] = 8
		self[Y_DIVS_KEY] = 8
		self[Y_AXIS_LABEL] = y_axis_label
		self[FRAME_RATE_KEY] = frame_rate
		self[TRIGGER_LEVEL_KEY] = 0
		self[TRIGGER_CHANNEL_KEY] = 0
		self[TRIGGER_MODE_KEY] = trig_mode

		self[TRIGGER_SLOPE_KEY] = wxgui.TRIG_SLOPE_POS
		self[T_FRAC_OFF_KEY] = 0.5
		self[USE_PERSISTENCE_KEY] = use_persistence
		self[PERSIST_ALPHA_KEY] = persist_alpha

		if self[TRIGGER_MODE_KEY] == wxgui.TRIG_MODE_STRIPCHART:
			self[T_FRAC_OFF_KEY] = 0.0

		for i in range(num_inputs):
			self.proxy(common.index_key(AC_COUPLE_KEY, i), controller, common.index_key(ac_couple_key, i))
		#init panel and plot
		wx.Panel.__init__(self, parent, style=wx.SIMPLE_BORDER)
		self.plotter = my_plotter(self)
		self.plotter.SetSize(wx.Size(*size))
		self.plotter.SetSizeHints(*size)
		self.plotter.set_title(title)
		self.plotter.enable_legend(True)
		self.plotter.enable_point_label(True)
		self.plotter.enable_grid_lines(True)
                self.plotter.set_use_persistence(use_persistence)
                self.plotter.set_persist_alpha(persist_alpha)
		#setup the box with plot and controls
		self.control_panel = scope_window.control_panel(self)
		main_box = wx.BoxSizer(wx.HORIZONTAL)
		main_box.Add(self.plotter, 1, wx.EXPAND)
		main_box.Add(self.control_panel, 0, wx.EXPAND)
		self.SetSizerAndFit(main_box)
		#register events for message
		self.subscribe(MSG_KEY, self.handle_msg)
		#register events for grid
		for key in [common.index_key(MARKER_KEY, i) for i in range(self.num_inputs)] + [
			TRIGGER_LEVEL_KEY, TRIGGER_MODE_KEY,
			T_PER_DIV_KEY, X_PER_DIV_KEY, Y_PER_DIV_KEY,
			T_OFF_KEY, X_OFF_KEY, Y_OFF_KEY,
			T_DIVS_KEY, X_DIVS_KEY, Y_DIVS_KEY,
			XY_MODE_KEY, AUTORANGE_KEY, T_FRAC_OFF_KEY,
			TRIGGER_SHOW_KEY, XY_MARKER_KEY, X_CHANNEL_KEY, Y_CHANNEL_KEY,
		]: self.subscribe(key, self.update_grid)
                #register events for plotter settings
		self.subscribe(USE_PERSISTENCE_KEY, self.plotter.set_use_persistence)
		self.subscribe(PERSIST_ALPHA_KEY, self.plotter.set_persist_alpha)
		#initial update
		self.update_grid()

	def handle_samples(self):
		"""
		Handle the cached samples from the scope input.
		Perform ac coupling, triggering, and auto ranging.
		"""
		if not self.sampleses: return
		sampleses = self.sampleses
		#if self[XY_MODE_KEY]:
                if True:
			self[DECIMATION_KEY] = 1
			x_samples = sampleses[self[X_CHANNEL_KEY]]
			y_samples = sampleses[self[Y_CHANNEL_KEY]]
                        z_samples = sampleses[2]
			#autorange
			if self[AUTORANGE_KEY] and time.time() - self.autorange_ts > AUTORANGE_UPDATE_RATE:
				x_min, x_max = common.get_min_max(x_samples)
				y_min, y_max = common.get_min_max(y_samples)
				#adjust the x per div
				x_per_div = common.get_clean_num((x_max-x_min)/self[X_DIVS_KEY])
				if x_per_div != self[X_PER_DIV_KEY]: self[X_PER_DIV_KEY] = x_per_div; return
				#adjust the x offset
				x_off = x_per_div*round((x_max+x_min)/2/x_per_div)
				if x_off != self[X_OFF_KEY]: self[X_OFF_KEY] = x_off; return
				#adjust the y per div
				y_per_div = common.get_clean_num((y_max-y_min)/self[Y_DIVS_KEY])
				if y_per_div != self[Y_PER_DIV_KEY]: self[Y_PER_DIV_KEY] = y_per_div; return
				#adjust the y offset
				y_off = y_per_div*round((y_max+y_min)/2/y_per_div)
				if y_off != self[Y_OFF_KEY]: self[Y_OFF_KEY] = y_off; return
				self.autorange_ts = time.time()
			#plot xy channel
			self.plotter.set_waveform(
				channel='XY',
				samples=(x_samples, y_samples, z_samples),
				color_spec=CHANNEL_COLOR_SPECS[0],
				marker=self[XY_MARKER_KEY],
			)
			#turn off each waveform
			for i, samples in enumerate(sampleses):
				self.plotter.clear_waveform(channel='Ch%d'%(i+1))
		else:
			#autorange
			if self[AUTORANGE_KEY] and time.time() - self.autorange_ts > AUTORANGE_UPDATE_RATE:
				bounds = [common.get_min_max(samples) for samples in sampleses]
				y_min = numpy.min([bound[0] for bound in bounds])
				y_max = numpy.max([bound[1] for bound in bounds])
				#adjust the y per div
				y_per_div = common.get_clean_num((y_max-y_min)/self[Y_DIVS_KEY])
				if y_per_div != self[Y_PER_DIV_KEY]: self[Y_PER_DIV_KEY] = y_per_div; return
				#adjust the y offset
				y_off = y_per_div*round((y_max+y_min)/2/y_per_div)
				if y_off != self[Y_OFF_KEY]: self[Y_OFF_KEY] = y_off; return
				self.autorange_ts = time.time()
			#number of samples to scale to the screen
			actual_rate = self.get_actual_rate()
			time_span = self[T_PER_DIV_KEY]*self[T_DIVS_KEY]
			num_samps = int(round(time_span*actual_rate))
			#handle the time offset
			t_off = self[T_FRAC_OFF_KEY]*(len(sampleses[0])/actual_rate - time_span)
			if t_off != self[T_OFF_KEY]: self[T_OFF_KEY] = t_off; return
			samps_off = int(round(actual_rate*self[T_OFF_KEY]))
			#adjust the decim so that we use about half the samps
			self[DECIMATION_KEY] = int(round(
					time_span*self[SAMPLE_RATE_KEY]/(0.5*len(sampleses[0]))
				)
			)
			#num samps too small, auto increment the time
			if num_samps < 2: self[T_PER_DIV_KEY] = common.get_clean_incr(self[T_PER_DIV_KEY])
			#num samps in bounds, plot each waveform
			elif num_samps <= len(sampleses[0]):
				for i, samples in enumerate(sampleses):
					#plot samples
					self.plotter.set_waveform(
						channel='Ch%d'%(i+1),
						samples=samples[samps_off:num_samps+samps_off],
						color_spec=CHANNEL_COLOR_SPECS[i],
						marker=self[common.index_key(MARKER_KEY, i)],
						trig_off=self.trigger_offset,
					)
			#turn XY channel off
			self.plotter.clear_waveform(channel='XY')
		#keep trigger level within range
		if self[TRIGGER_LEVEL_KEY] > self.get_y_max():
			self[TRIGGER_LEVEL_KEY] = self.get_y_max(); return
		if self[TRIGGER_LEVEL_KEY] < self.get_y_min():
			self[TRIGGER_LEVEL_KEY] = self.get_y_min(); return
		#disable the trigger channel
		if not self[TRIGGER_SHOW_KEY] or self[XY_MODE_KEY] or self[TRIGGER_MODE_KEY] == wxgui.TRIG_MODE_FREE:
			self.plotter.clear_waveform(channel='Trig')
		else: #show trigger channel
			trigger_level = self[TRIGGER_LEVEL_KEY]
			trigger_point = (len(self.sampleses[0])-1)/self.get_actual_rate()/2.0
			self.plotter.set_waveform(
				channel='Trig',
				samples=(
					[self.get_t_min(), trigger_point, trigger_point, trigger_point, trigger_point, self.get_t_max()],
					[trigger_level, trigger_level, self.get_y_max(), self.get_y_min(), trigger_level, trigger_level]
				),
				color_spec=TRIGGER_COLOR_SPEC,
			)
		#update the plotter
		self.plotter.update()

	def update_grid(self, *args):
		"""
		Update the grid to reflect the current settings:
		xy divisions, xy offset, xy mode setting
		"""
		if self[T_FRAC_OFF_KEY] < 0: self[T_FRAC_OFF_KEY] = 0; return
		if self[T_FRAC_OFF_KEY] > 1: self[T_FRAC_OFF_KEY] = 1; return
		#if self[XY_MODE_KEY]:
                if True:
			#update the x axis
			self.plotter.set_x_label('Ch%d'%(self[X_CHANNEL_KEY]+1))
			self.plotter.set_x_grid(self.get_x_min(), self.get_x_max(), self[X_PER_DIV_KEY])
			#update the y axis
			self.plotter.set_y_label('Ch%d'%(self[Y_CHANNEL_KEY]+1))
			self.plotter.set_y_grid(self.get_y_min(), self.get_y_max(), self[Y_PER_DIV_KEY])
		else:
			#update the t axis
			self.plotter.set_x_label('Time', 's')
			self.plotter.set_x_grid(self.get_t_min(), self.get_t_max(), self[T_PER_DIV_KEY], True)
			#update the y axis
			self.plotter.set_y_label(self[Y_AXIS_LABEL])
			self.plotter.set_y_grid(self.get_y_min(), self.get_y_max(), self[Y_PER_DIV_KEY])
		#redraw current sample
		self.handle_samples()


class crt_f(gr.hier_block2, common.wxgui_hb):
    """
    docstring for block crt_f
    """
    def __init__(self, parent, title='', sample_rate=1):
        num_inputs = 3
	gr.hier_block2.__init__(
            self,
            "scope_sink",
            gr.io_signature(num_inputs, num_inputs, gr.sizeof_float),
            gr.io_signature(0, 0, 0),
	)
        msgq = gr.msg_queue(2)
        scope = wxgui.oscope_sink_f(sample_rate, msgq)
	self.controller = pubsub()
	self.controller.subscribe(SAMPLE_RATE_KEY, scope.set_sample_rate)
	self.controller.publish(SAMPLE_RATE_KEY, scope.sample_rate)
	self.controller.subscribe(DECIMATION_KEY, scope.set_decimation_count)
	self.controller.publish(DECIMATION_KEY, scope.get_decimation_count)
	self.controller.subscribe(TRIGGER_LEVEL_KEY, scope.set_trigger_level)
	self.controller.publish(TRIGGER_LEVEL_KEY, scope.get_trigger_level)
	self.controller.subscribe(TRIGGER_MODE_KEY, scope.set_trigger_mode)
	self.controller.publish(TRIGGER_MODE_KEY, scope.get_trigger_mode)
	self.controller.subscribe(TRIGGER_SLOPE_KEY, scope.set_trigger_slope)
	self.controller.publish(TRIGGER_SLOPE_KEY, scope.get_trigger_slope)
	self.controller.subscribe(TRIGGER_CHANNEL_KEY, scope.set_trigger_channel)
	self.controller.publish(TRIGGER_CHANNEL_KEY, scope.get_trigger_channel)
	for i in range(num_inputs):
		self.controller[common.index_key(AC_COUPLE_KEY, i)] = False
	common.input_watcher(msgq, self.controller, MSG_KEY)
	#create window
	self.win = my_scope_window(
		parent=parent,
		controller=self.controller,
		size=(600, 300),
		title=title,
		frame_rate=60, #scope_window.DEFAULT_FRAME_RATE,
		num_inputs=num_inputs,
		sample_rate_key=SAMPLE_RATE_KEY,
		t_scale=0.1,
		v_scale=1,
		v_offset=0,
		xy_mode=False,
		trig_mode=wxgui.TRIG_MODE_FREE,
		y_axis_label='Counts',
		ac_couple_key=AC_COUPLE_KEY,
		trigger_level_key=TRIGGER_LEVEL_KEY,
		trigger_mode_key=TRIGGER_MODE_KEY,
		trigger_slope_key=TRIGGER_SLOPE_KEY,
		trigger_channel_key=TRIGGER_CHANNEL_KEY,
		decimation_key=DECIMATION_KEY,
		msg_key=MSG_KEY,
                use_persistence=True,
                persist_alpha=0.001,
	)
	common.register_access_methods(self, self.win)
	for i in range(num_inputs):
		self.wxgui_connect(
			(self, i),
			ac_couple_block(self.controller, common.index_key(AC_COUPLE_KEY, i), SAMPLE_RATE_KEY),
			(scope, i),
		)

#    def work(self, input_items, output_items):
#        in0 = input_items[0]
#        # <+signal processing here+>
#        return len(input_items[0])

