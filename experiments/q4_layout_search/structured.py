import sys,math,json;sys.path.insert(0,'experiments/q4_layout_search')
import numpy as np
from layout_opt import grid,objective,tour,ring
G=grid(40.);res=[]
for center in (1,0):
    for n_in in (6,7,8,9):
        for r_in in (800,850,900,950,1000,1050):
            for r_out in (1884,1892,1900):
                for ph_in in (0.,math.pi/n_in):
                    S=([np.zeros(2)] if center else [])+ring(n_in,r_in,ph_in)+ring(12,r_out,math.pi/12)
                    val,w=objective(S,G,20.)
                    res.append((val,len(S),center,n_in,r_in,r_out,round(ph_in,3)))
res.sort(reverse=True)
for r in res[:25]:print(r)
json.dump(res,open('experiments/q4_layout_search/structured.json','w'))
