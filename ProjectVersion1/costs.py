#
# Optimal Control of a Vehicle
# Cost Functions
# Rapallini Antonio & Bertamè Sebastiano 
# Bologna, 04/01/2024
#

import numpy as np
import Dynamics as dyn

# Import the number of states of the choosen dinamics
ns = dyn.ns
ni = dyn.ni

# Define Cost Matrices accordingly on the choosen dynamics
if ns == 2:
    QQt = 0.1*np.diag([100.0, 1.0])
    RRt = 0.01*np.eye(ni)
    QQT = QQt   # Terminal cost matrix

if ns == 6:
    QQt = 0.1*np.diag([1.0, 1.0, 1000.0, 10000.0, 1000.0, 1000.0])    # cost for xx = [x,y,psi,V,Beta,psidot]
    RRt = 0.1*np.diag([1000.0, 0.0001])                               # costs for uu = [Delta,F]
    QQT = QQt   # Terminal cost matrix
    
#######################################
# Stage Cost function
#######################################

def stagecost(xx, uu, xx_ref, uu_ref):

    xx = xx[:, None]
    uu = uu[:, None]
    xx_ref = xx_ref[:, None]
    uu_ref = uu_ref[:, None]

    ll = 0.5 * (xx - xx_ref).T @ QQt @ (xx - xx_ref) + 0.5 * (uu - uu_ref).T @ RRt @ (uu - uu_ref)
    lx = QQt @ (xx - xx_ref)
    lu = RRt @ (uu - uu_ref)
    
    lxx = QQt
    luu = RRt
    lux = np.zeros((ni, ns))

    return ll.squeeze(), lx, lu, lxx, luu, lux


#######################################
# Terminal cost fucntion
#######################################

def termcost(xx, xx_ref):

    xx = xx[:, None]
    xx_ref = xx_ref[:, None]

    llT = 0.5 * (xx - xx_ref).T @ QQT @ (xx - xx_ref)
    lTx = QQT @ (xx - xx_ref)
    lTxx = QQT

    return llT.squeeze(), lTx, lTxx