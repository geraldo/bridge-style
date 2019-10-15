import os
import math
import json

_warnings = []

def convertToDict(geostyler):
    global _warnings
    _warnings = []
    global _symbols
    _symbols = []
    layer = processLayer(geostyler)
    return layer


def convert(geostyler):
    d = convertToDict(geostyler)
    mapfile = convertDictToMapfile(d)
    symbols = convertDictToMapfile({"SYMBOLS": _symbols})
    return mapfile, symbols, _warnings

def convertDictToMapfile(d):    
    def _toString(element, indent):
        s = ""
        INDENT = "  " * indent        
        for k,v in element.items():
            if isinstance(v, dict):
                s += "%s%s\n" % (INDENT ,  k)
                s += _toString(v, indent + 1)
                s += INDENT + "END\n"
            elif isinstance(v, list):
                for item in v:
                    s+= _toString(item, indent)
            elif isinstance(v, tuple):
                s += "%s%s %s\n" % (INDENT, k, " ".join([str(item) for item in  v]))
            else:
                s += "%s%s %s\n" % (INDENT, k, v)

        return s
            
    return _toString(d, 0)

def processLayer(layer):
    classes = []
    
    for rule in layer.get("rules", []):
        clazz = processRule(rule)
        classes.append(clazz)

    layerData ={"LAYER":
                    {
                    "NAME": _quote(layer.get("name", "")),
                    "DATA": _quote("{data}" ),
                    "STATUS": "ON",
                    "TYPE": "{layertype}",
                    "SIZEUNITS": "pixels",
                    "CLASSES": classes
                    }
                }    
    return layerData


def processRule(rule):
    d = {"NAME": _quote(rule.get("name", "") or "default")}
    name = rule.get("name", "rule")
    
    expression = convertExpression(rule.get("filter", None))
    if expression is not None:
        d["EXPRESSION"] = expression
    
    styles = [{"STYLE": processSymbolizer(s)} for s in rule["symbolizers"]]

    if "scaleDenominator" in rule:
        scale = rule["scaleDenominator"]
        if "max" in scale:
            d["MAXSCALEDENOM"] = scale["max"]
        if "min" in scale:
            d["MINSCALEDENOM"] = scale["min"]
    
    d["STYLES"] = styles

    return {"CLASS": d}

func = {"Or": "OR", 
         "And": "AND", 
         "PropertyIsEqualTo": "=",
         "PropertyIsNotEqualTo": "!=",
         "PropertyIsLessThanOrEqualTo": "<=", 
         "PropertyIsGreaterThanOrEqualTo": ">=",
         "PropertyIsLessThan": "<", 
         "PropertyIsGreaterThan": ">", 
         "Add": "+", 
         "Sub": "-", 
         "Mul": "*", 
         "Div": "/", 
         "Not": "!",
         "PropertyName": "PropertyName"
         } #TODO

def convertExpression(exp):
    if exp is None:
        return None
    if isinstance(exp, list):
        funcName = func.get(exp[0], None)        
        if funcName is None:
            _warnings.append("Unsupported expression function for MapServer conversion: '%s'" % exp[0])
            return None
        elif funcName == "PropertyName":
            return "[%s]" % exp[1]
        else:
            arg1 = convertExpression(exp[1])
            if len(exp) == 3:                
                arg2 = convertExpression(exp[2])
                return "(%s %s %s)" % (arg1, funcName, arg2)
            else:
                return "%s(%s)" % (funcName, arg1)                    
    else:
        try:
            f = float(exp)
            return exp
        except:
            return _quote(exp)

def processSymbolizer(sl):
    symbolizerType = sl["kind"]
    if symbolizerType == "Icon":
        symbolizer = _iconSymbolizer(sl)
    if symbolizerType == "Line":
        symbolizer = _lineSymbolizer(sl)            
    if symbolizerType == "Fill":
        symbolizer = _fillSymbolizer(sl)
    if symbolizerType == "Mark":
        symbolizer = _markSymbolizer(sl)
    if symbolizerType == "Text":
        symbolizer = _textSymbolizer(sl)
    if symbolizerType == "Raster":
        symbolizer = _rasterSymbolizer(sl)        

    geom = _geometryFromSymbolizer(sl)
    if geom is not None:
        _warnings.append("Derived geometries are not supported in mapbox gl")

    return symbolizer

def _symbolProperty(sl, name):
    if name in sl:        
        return convertExpression(sl[name])      
    else:
        return None

def _textSymbolizer(sl):
    style = {} 
    color = _symbolProperty(sl, "color")
    fontFamily = _symbolProperty(sl, "font")
    label = _symbolProperty(sl, "label")
    size = _symbolProperty(sl, "size")
    if "offset" in sl:
        offset = sl["offset"]
        offsetx = convertExpression(offset[0])
        offsety = convertExpression(offset[1])
        style["OFFSET"] = (offsetx, offsety)

    style["TEXT"] = label    
    style["SIZE"] = size
    style["FONT"] =  fontFamily
    style["TYPE"] = "truetype"
    style["COLOR"] = _quote(color)

    '''
    if "haloColor" in sl and "haloSize" in sl:        
        paint["text-halo-width"] =  _symbolProperty(sl, "haloSize")   
        paint["text-halo-color"] = _symbolProperty(sl, "haloColor")
    
    rotation = -1 * float(qgisLayer.customProperty("labeling/angleOffset"))
    layout["text-rotate"] = rotation

    ["text-opacity"] = (255 - int(qgisLayer.layerTransparency())) / 255.0

    if str(qgisLayer.customProperty("labeling/scaleVisibility")).lower() == "true":
        layer["minzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMin")))
        layer["maxzoom"]  = _toZoomLevel(float(qgisLayer.customProperty("labeling/scaleMax")))
    '''

    return {"LABEL": style}

def _lineSymbolizer(sl, graphicStrokeLayer = 0):
    opacity = _symbolProperty(sl, "opacity")
    color =  sl.get("color", None)
    graphicStroke =  sl.get("graphicStroke", None)
    width = _symbolProperty(sl, "width")
    try:
        float(width)      
    except:
        _warnings.append("Only pixels are supported as measure units for MapServer conversion")
        width = 1    
    dasharray = _symbolProperty(sl, "dasharray")
    cap = _symbolProperty(sl, "cap")
    join = _symbolProperty(sl, "join")
    offset = _symbolProperty(sl, "offset")

    style = {}
    if graphicStroke is not None:
        _warnings.append("Marker lines not supported for MapServer conversion")
        #TODO

    if color is not None:
        style["WIDTH"] = width
        style["OPACITY"] = opacity
        style["COLOR"] = _quote(color)
        style["LINECAP"] = cap
        style["LINEJOIN"] = join
    if dasharray is not None:
        style["PATTERN"] = dasharray
    if offset is not None:
        style["OFFSET"] = "%s -99" % str(offset)
    
    return style
    
def _geometryFromSymbolizer(sl):
    geomExpr = convertExpression(sl.get("geometry", None))
    return geomExpr       

def _iconSymbolizer(sl):
    path = os.path.basename(sl["image"])
    rotation = _symbolProperty(sl, "rotate") or 0
    size = _symbolProperty(sl, "size")    
    color = _symbolProperty(sl, "color")
    style = {}
    style["SYMBOL"] = path
    style["ANGLE"] = rotation
    style["COLOR"] = _quote(color)
    style["SIZE"] = size

    return style
    
def _markSymbolizer(sl):
    #outlineDasharray = _symbolProperty(sl, "strokeDasharray")
    #opacity = _symbolProperty(sl, "opacity")
    size = _symbolProperty(sl, "size")
    rotation = _symbolProperty(sl, "rotate") or 0
    shape = _symbolProperty(sl, "wellKnownName")
    color = _symbolProperty(sl, "color")
    outlineColor = _symbolProperty(sl, "strokeColor")
    outlineWidth = _symbolProperty(sl, "strokeWidth")    

    style = {}  
    if shape.startswith("file://"):
        svgFilename = shape.split("//")[-1]
        svgName = os.path.splitext(svgFilename)[0]
        name = "svgicon_" + svgName
        _symbols.append({"SYMBOL":{"TYPE": "svg", "IMAGE": svgFilename, "NAME": name}})
    else:
        name = shape
    style["SYMBOL"] = _quote(name)
    style["COLOR"] = _quote(color)
    style["SIZE"] = size
    style["ANGLE"] = rotation
    if outlineColor is not None:                
        style["OUTLINECOLOR"] = _quote(outlineColor)
        style["OUTLINEWIDTH"] = outlineWidth

    return style

def _fillSymbolizer(sl):
    style = {}
    opacity = _symbolProperty(sl, "opacity")
    color =  sl.get("color", None)
    graphicFill =  sl.get("graphicFill", None)
    if graphicFill is not None:
        _warnings.append("Marker fills not supported for MapServer conversion")
        #TODO
    style["OPACITY"] = opacity
    if color is not None:                
        style["COLOR"] = _quote(color)

    outlineColor = _symbolProperty(sl, "outlineColor")
    if outlineColor is not None:
        outlineWidth = _symbolProperty(sl, "outlineWidth") 
        style["OUTLINECOLOR"] = _quote(outlineColor)
        style["OUTLINEWIDTH"] = outlineWidth

    return style

def _rasterSymbolizer(sl):
    return None

def _quote(t):
    return '"%s"' % t