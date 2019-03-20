from __future__ import print_function
import math
from lxml import etree
from mapproxy.compat import string_type
from mapproxy.request.wms import switch_bbox_epsg_axis_order

class WMTSCapabilities(object):
    version = '1.0.0'

    def __init__(self, tree):
        self.tree = tree
        self._layer_tree = None
        self.namespaces = tree.getroot().nsmap

    def findtext(self, tree, xpath):
        x = tree.find(xpath, self.namespaces)
        return x.text.strip() if x is not None else ''

    def find(self, tree, xpath):
        return tree.find(xpath, self.namespaces)

    def findall(self, tree, xpath):
        return tree.findall(xpath, self.namespaces)

    @staticmethod
    def attrib(elem, name):
        return elem.attrib[name] if name in elem.attrib else None

    def layers_list(self):
        return self.layers()

    def metadata(self):
        elem = self.find(self.tree, '/ows:ServiceIdentification')
        if elem is None or len(elem) is 0:
            return {}

        md = dict(
            title = self.findtext(elem, 'ows:Title'),
            abstract = self.findtext(elem, 'ows:Abstract'),
            service_type = self.findtext(elem, 'ows:ServiceType'),
            service_type_version = self.findtext(elem, 'ows:ServiceTypeVersion'),
            access_constraints = self.findtext(elem, 'ows:AccessConstraints'),
        )

        md['contact'] = self.parse_contact()
        return md

    def parse_contact(self):
        elem = self.find(self.tree, 'ows:ServiceProvider')
        if elem is None or len(elem) is 0:
            return {}

        md = dict(
            organization = self.findtext(elem, 'ows:ProviderName'),
        )

        elem = self.find(self.tree, 'ows:ProviderSite')
        if elem is not None:
            md['website'] = self.attrib(elem, 'xlink:href')

        elem = self.find(self.tree, 'ows:ServiceContact')
        if elem is not None:
            md['name'] = self.findtext(elem, 'ows:IndividualName')

            inner = self.find(elem, 'ows:ContactInfo')
            if inner is not None:

                md['phone'] = self.findtext(inner, 'ows:Phone/ows:Voice')
                md['address'] = self.findtext(inner, 'ows:Address/ows:DeliveryPoint')
                md['city'] = self.findtext(inner, 'ows:Address/ows:City')
                md['postcode'] = self.findtext(inner, 'ows:Address/ows:PostalCode')
                md['country'] = self.findtext(inner, 'ows:Address/ows:Country')
                md['email'] = self.findtext(inner, 'ows:Address/ows:ElectronicMailAddress')

        return md

    def layers(self):
        if not self._layer_tree:
            root_layer = self.find(self.tree, '//Contents')
            # print('l', root_layer, self.tree)
            self._layer_tree = self.parse_layer(root_layer, None)

        return self._layer_tree

    def requests(self, elem):
        resource = self.find(elem, 'ResourceURL')
        resources = {}
        # resource = self.find(requests_elem, 'GetMap/DCPType/HTTP/Get/OnlineResource')
        if resource != None:
            resources['format'] = self.attrib(resource, 'format')
            resources['resourceType'] = self.attrib(resource, 'resourceType')
            resources['template'] = self.attrib(resource, 'template')
        return resources

    def parse_layer(self, layer_elem, parent_layer):
        child_layers = []
        # layer = self.parse_layer_data(layer_elem, parent_layer or {})
        child_layer_elems = self.findall(layer_elem, 'Layer')

        for child_elem in child_layer_elems:
            child_layers.append(self.parse_layer_data(child_elem, layer_elem))
            # child_layers.append(self.parse_layer(child_elem, layer))

        # layer['layers'] = child_layers
        # return layer
        return child_layers

    def parse_layer_data(self, elem, parent_layer):
        layer = dict(
            title=self.findtext(elem, 'ows:Title'),
            abstract=self.findtext(elem, 'ows:Abstract'),
            name=self.findtext(elem, 'ows:Identifier'),
            format=self.findtext(elem, 'Format'),
            opaque=False,
            queryable=True,
        )

        layer['bbox_srs'] = self.layer_bbox_srs(elem)#, parent_layer)
        layer['url'] = self.requests(elem)
        layer['style'] = self.layer_style(elem)
        layer['tmsl'] = self.layer_tmsl(elem)
        # TODO: enhance this with tilematrix data
        layer['srs'] = ['EPSG:4326']

        return layer

    def layer_tmsl(self, elem):
        elems = self.findall(elem, 'TileMatrixSetLink')
        x = []
        if len(elems) > 0:
            for e in elems:
                if e != None:
                    x.append(self.findtext(e, 'TileMatrixSet'))
        return x

    def layer_style(self, elem):
        elem = self.find(elem, 'Style')
        x = {}
        if elem != None:
            x['isDefault'] = self.attrib(elem, 'isDefault')
            x['ows:Title'] = self.findtext(elem, 'ows:Title')
            x['ows:Identifier'] = self.findtext(elem, 'ows:Identifier')
        return x

    def layer_bbox_srs(self, elem):#, parent_layer=None):
        bbox_srs = {}

        wrappers = {
            'UNK': 'ows:BoundingBox', 
            'WGS84': 'ows:WGS84BoundingBox',
        }
        for srs, w in wrappers.items():
            bbox_srs_elems = self.findall(elem, w)
            if len(bbox_srs_elems) > 0:
                for bbox_srs_elem in bbox_srs_elems:
                    crs = self.attrib(bbox_srs_elem, 'crs')
                    bbox = (
                        self.findtext(bbox_srs_elem, 'ows:LowerCorner'),
                        self.findtext(bbox_srs_elem, 'ows:UpperCorner'),
                    )
                    bbox = [float(y) for x in bbox for y in x.split(' ')]
                    bbox_srs[w] = {
                        'srs': srs,
                        'crs': crs,
                        'bbox': bbox,
                    }

        return bbox_srs


def yaml_sources(cap):
    sources = {}
    for layer in cap.layers():
        layer_name = layer['name'] + '_wmts'

        sources[layer_name] = dict(
            type='wmts',
            layer=layer,
        )

    import yaml
    print(yaml.dump(dict(sources=sources), default_flow_style=False))

def parse_capabilities(fileobj):
    if isinstance(fileobj, string_type):
        fileobj = open(fileobj, 'rb')
    tree = etree.parse(fileobj)
    root_tag = tree.getroot().tag

    if root_tag == '{http://www.opengis.net/wmts/1.0}Capabilities':
        return WMTSCapabilities(tree)
    else:
        raise ValueError('unknown start tag in capabilities: ' + root_tag)

if __name__ == '__main__':
    import sys
    cap = parse_capabilities(sys.argv[1])
    yaml_sources(cap)
