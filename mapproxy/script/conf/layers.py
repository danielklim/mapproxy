# -:- encoding: utf-8 -:-
# This file is part of the MapProxy project.
# Copyright (C) 2013 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

def layers(cap, caches, _type='wms'):
    if _type == 'wms':
        return [_layer_wms(cap.layers(), caches)]
    elif _type == 'wmts':
        return _layer_wmts(cap.layers(), caches)

def _layer_wms(layer, caches):
    name, conf = for_layer(layer, caches, 'wms')
    child_layers = []

    for child_layer in layer['layers']:
        child_layers.append(_layer_wms(child_layer, caches))

    if child_layers:
        conf['layers'] = child_layers

    return conf

def _layer_wmts(layer, caches):
    layers = []
    for l in layer:
        layers.append(for_layer(l, caches, 'wmts'))
    return layers

def for_layer(layer, caches, _type='wms'):
    conf = {
        'title': layer['title'],
    }
    suffix = '_{}'.format(_type)

    if layer['name']:
        conf['name'] = layer['name']

        if layer['name'] + '_cache' in caches:
            conf['sources'] = [layer['name'] + '_cache']
        else:
            conf['sources'] = [layer['name'] + suffix]

    md = {}
    if layer['abstract']:
        md['abstract'] = layer['abstract']

    if md:
        conf['md'] = md

    return layer['name'], conf

