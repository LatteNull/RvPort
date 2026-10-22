"""手工标量语法，避免用被测分析器输出生成预期。"""
def row(start, end, kind, parent=None, fields=None, children=(), text="", binding=None):
    key = (start, end, kind)
    result = {"key": key, "kind": kind, "parent": parent, "fields": fields or {},
              "children": tuple(children), "text": text, "operator": "", "span": (1,start+1,1,end+1)}
    if binding is not None:
        result["binding"] = binding
    return result


def straight_rows():
    f=(0,100,"function_definition"); b=(10,100,"compound_statement")
    d=(11,30,"declaration"); t=(11,14,"primitive_type"); init=(15,29,"init_declarator")
    name=(15,16,"identifier"); value=(20,28,"call_expression"); callee=(20,22,"identifier")
    stmt=(40,80,"expression_statement"); call=(40,79,"call_expression"); a=(40,46,"identifier")
    args=(46,79,"argument_list"); use=(48,49,"identifier")
    records = [
        row(*f,fields={"body":b},children=(b,)),
        row(*b,parent=f,children=(d,stmt)),
        row(*d,parent=b,fields={"type":t,"declarator":init},children=(t,init)),
        row(*t,parent=d,text="int"),
        row(*init,parent=d,fields={"declarator":name,"value":value},children=(name,value)),
        row(*name,parent=init,text="v",binding={"status":"bound","declaration":name,"role":"declaration"}),
        row(*value,parent=init,fields={"function":callee},children=(callee,)),
        row(*callee,parent=value,text="_x"),
        row(*stmt,parent=b,children=(call,)),
        row(*call,parent=stmt,fields={"function":a,"arguments":args},children=(a,args)),
        row(*a,parent=call,text="assert"),
        row(*args,parent=call,children=(use,)),
        row(*use,parent=args,text="v",binding={"status":"bound","declaration":name,"role":"read"}),
    ]
    return records


def function(records=None, name="main", **extra):
    return {"name":name,"plain":True,"span":(1,1,1,101),"nameSpan":(1,1,1,5),
            "bodySpan":(1,11,1,101),"nestedSpans":(),"records":straight_rows() if records is None else records,
            "status":"complete","reasonCodes":(),**extra}


def data(*functions, **extra):
    return {"functions":functions or (function(),),"status":"complete","reasonCodes":(),"recordCount":14,**extra}
