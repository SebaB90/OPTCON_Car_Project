#
# OPTCON PROJECT 
# Optimal Control of a Veichle
# Antonio Rapallini & Sebastiano Bertamé
# Bologna, 22/11/2022
#

import numpy as np
import scipy as sp
import matplotlib
import matplotlib.pyplot as plt
import Dynamics as dyn
# import Gradient as grad
import Newton as nwtn
from scipy.optimize import fsolve
from scipy.interpolate import PchipInterpolator
from Newton import Newton


# Allow Ctrl-C to work despite plotting
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

##################################
##### TASK 0: DISCRETIZATION #####
##################################


#define params

dt = dyn.dt           #sample time
dx = 1e-3           #infinitesimal increment
du = 1e-3           #infinitesimal increment
ns = dyn.ns              #number of states
ni = dyn.ni              #number of inputs
max_iters = 20      #maximum number of iterations for Newton's method

m = 1480    #Kg
Iz = 1950   #Kg*m^2
a = 1.421   #m
b = 1.029   #m
mi = 1      #nodim
g = 9.81    #m/s^2

tf = dyn.TT            #discrete time samples
T = dyn.T              #time instants
T_mid = dyn.T_mid      #half time
term_cond = 1e-6       #terminal condition

plot = True
Task0 = False

if Task0 :
    # defining x and u
    u = np.array([0.25, 20])
    x = np.array([0, 0, 0, 1, 0, 0])

    x_plus, fx, fu = dyn.dynamics(x, u)

    A = fx.T
    B = fu.T

    # OPEN LOOP TEST to check if the dynamics do what expected ---------------------------------------------------
    if plot:
        x_traj = [np.copy(x[0])]
        y_traj = [np.copy(x[1])]
        traj = np.copy(x)

        total_time = 100                     # Adjust the total simulation time as needed
        num_steps = int(total_time / dt)

        for i in range(num_steps-1):
            traj = dyn.dynamics(traj, u)[0]
            x_traj.append(traj[0])
            y_traj.append(traj[1])

        # Plotting the trajectory
        
        fig, axs = plt.subplots(3, 1, sharex='all')

        axs[0].plot(x_traj, y_traj, 'g', linewidth=2)
        axs[0].grid()
        axs[0].set_ylabel('$y$')
        axs[0].set_xlabel('$x$')

        axs[1].plot(np.linspace(0, tf, num_steps), x_traj, 'g', linewidth=2)
        axs[1].grid()
        axs[1].set_ylabel('$x$')
        
        axs[2].plot(np.linspace(0, tf, num_steps), y_traj, 'g', linewidth=2)
        axs[2].grid()
        axs[2].set_ylabel('$y$')
        axs[2].set_xlabel('time')

        #fig.align_ylabels(axs)

        plt.show()

    # Checking derivatives

    # CHECK IF THE DERIVATIVES ARE CORRECT ----------------------------------------------------------------------

    xdx = np.zeros((ns,))
    ddx = np.zeros((ns,))
    udu = np.zeros((ni,))
    ddu = np.zeros((ni,))

    for i in range (0,ns):
        ddx[i] = dx

    for k in range (0,ni):
        ddu[k] = du

    xdx = x + ddx
    xx_plus = dyn.dynamics(xdx, u)[0]
    diff_x = xx_plus - x_plus
    check_x = diff_x - np.dot(A,ddx)

    udu = u + ddu
    xx_plus = dyn.dynamics(x, udu)[0]    
    diff_u = xx_plus - x_plus      
    check_u = diff_u - np.dot(B,ddu)

    print ('error in derivatives of x is:', check_x)
    print ('error in derivatives of u is:', check_u)


#########################################
##### TASK 1: TRAJECTORY GENERATION I ###
#########################################

# We have to find the eqilibria for the system, a way to do that is to use the cornering equilibria, those associated to the systems with Betadot, Vdot and Psidotdot = 0
# Once I have set them I can focus on the last three equation, then imposing Veq and PsidotEq (I can think of this also as Veq/R with R a certain imposed radious) we obtain Betaeq, Fxeq and Deltaeq, in alternative I can set Veq and Betaeq and as concequence find the other eqilibrium values.
# The associated x and y trajectory can then be obtained by forward integration of the dynamics with the values we just found.
# For vehicles these trajectories are called corering eqilibria, in which I have circles with some radious and some Veq.

# Evaluate the EQUILIBRIUM  ----------------------------------------------------------------------------------

eq = np.zeros((ns+ni, 2))
initial_guess = [0.1, 0.1, 0]          # [x5(0), u0(0), u1(0)]

# calculation of the parameters at equilibrium
def equations(vars):
    x5, u0, u1 = vars
    Beta = [u0 - (x3*np.sin(x4) + a*x5)/(x3*np.cos(x4)), - (x3*np.sin(x4) - b*x5)/(x3*np.cos(x4))]              # Beta = [Beta_f, Beta_r]
    Fz = [m*g*b/(a+b), m*g*a/(a+b)]                                                                             # Fz = [F_zf, F_zr]
    Fy = [mi*Fz[0]*Beta[0], mi*Fz[1]*Beta[1]]                                                                   # Fy = [F_yf, F_yr]

    eq1 = (Fy[1] * np.sin(x4) + u1 * np.cos(x4 - u0) + Fy[0] * np.sin(x4 - u0))/m                               # V dot (x3)
    eq2 = (Fy[1] * np.cos(x4) + Fy[0] * np.cos(x4 - u0) - u1 * np.sin(x4 - u0))/(m * x3) - x5                   # Beta dot (x4)
    eq3 = ((u1 * np.sin(u0) + Fy[0] * np.cos(u0)) * a - Fy[1] * b)/Iz                                           # Psi dot dot (x5)

    return [eq1, eq2, eq3]

# Initial guess for the solution

# FIRST EQUILIBRIUM
#imposing x3 and x4
x3 = 3                  
x4 = 0.1

eq[3,0] = np.copy(x3)                           # V
eq[4,0] = np.copy(x4)                           # beta
eq[5:,0] = fsolve(equations, initial_guess)     # psi dot, steering angle, force
eq[2,0] = eq[5,0]*int(tf/2)                               # psi   
eq[0,0] =(eq[3,0]*np.cos(eq[4,0])*np.cos(eq[2,0])-eq[3,0]*np.sin(eq[4,0])*np.sin(eq[2,0]))*int(tf/2)     # x
eq[1,0] =(eq[3,0]*np.cos(eq[4,0])*np.sin(eq[2,0])+eq[3,0]*np.sin(eq[4,0])*np.cos(eq[2,0]))*int(tf/2)     # y

# SECOND EQUILIBRIUM
x3 = 5                 
x4 = 0.25

eq[3,1] = np.copy(x3)                           # V
eq[4,1] = np.copy(x4)                           # beta
eq[5:,1] = fsolve(equations, initial_guess)     # psi dot, steering angle, force
eq[2,1] = eq[5,1]*int(tf/2)                               # psi   
eq[0,1] =(eq[3,1]*np.cos(eq[4,1])*np.cos(eq[2,1])-eq[3,1]*np.sin(eq[4,1])*np.sin(eq[2,1]))*int(tf/2)     # x
eq[1,1] =(eq[3,1]*np.cos(eq[4,1])*np.sin(eq[2,1])+eq[3,1]*np.sin(eq[4,1])*np.cos(eq[2,1]))*int(tf/2)     # y

# Print the result
print('Equilibrium 1:', eq[0:,0], '\nEquilibrium 2:', eq[0:,1])


# Design REFERENCE TRAJECTORY  ---------------------------------------------------------------------------------------

traj_ref = np.zeros((ns+ni, T))
traj_ref[3:,0] = eq[3:,0]

# Step reference signal - for all the states

for tt in range(1,T):
  
    traj = dyn.dynamics(traj_ref[:6,tt-1], traj_ref[6:,tt-1])[0]
    traj_ref[:3, tt] = traj[:3]

    if tt < T_mid:
        traj_ref[3:, tt] = eq[3:,0]

    else:  
        traj_ref[3:, tt] = eq[3:,1]

tt_hor = range(T)

####################################################################################################################################
### Plot to test trajectory reference
plt.plot(traj_ref[0,:], traj_ref[1,:], label='Trajectory')
plt.title('Vehicle Trajectory')
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.grid(True)
plt.show()
#######################################################################################################################################

fig, axs = plt.subplots(8, 1, sharex='all')

axs[0].plot(tt_hor, traj_ref[0,:], 'g--', linewidth=2)
axs[0].grid()
axs[0].set_ylabel('$x$')

axs[1].plot(tt_hor, traj_ref[1,:], 'g--', linewidth=2)
axs[1].grid()
axs[1].set_ylabel('$y$')

axs[2].plot(tt_hor, traj_ref[2,:], 'g--', linewidth=2)
axs[2].grid()
axs[2].set_ylabel('$psi$')

axs[3].plot(tt_hor, traj_ref[3,:], 'g--', linewidth=2)
axs[3].grid()
axs[3].set_ylabel('$V$')

axs[4].plot(tt_hor, traj_ref[4,:], 'g--', linewidth=2)
axs[4].grid()
axs[4].set_ylabel('$beta$')

axs[5].plot(tt_hor, traj_ref[5,:], 'g--', linewidth=2)
axs[5].grid()
axs[5].set_ylabel('$psi dot$')

axs[6].plot(tt_hor, traj_ref[6,:], 'g--', linewidth=2)
axs[6].grid()
axs[6].set_ylabel('$u_0$')

axs[7].plot(tt_hor, traj_ref[7,:], 'g--', linewidth=2)
axs[7].grid()
axs[7].set_ylabel('$u_1$')
axs[7].set_xlabel('time')

fig.align_ylabels(axs)

plt.show()

# NEWTON'S METHOD evaluation  ----------------------------------------------------------------------------------------

# arrays to store data
xx = np.zeros((ns, T, max_iters))   # state seq.
uu = np.zeros((ni, T, max_iters))   # input seq.
xx_ref = np.zeros((ns, T))          # state ref.
uu_ref = np.zeros((ni, T))          # input ref.

xx_ref = traj_ref[0:6,:]
uu_ref = traj_ref[6:,:]


# perform Newton's like method
if plot:
    xx, uu, descent, JJ = nwtn.Newton(xx_ref, uu_ref, max_iters)

    xx_star = xx[:,:,max_iters-1]
    uu_star = uu[:,:,max_iters-1]
    uu_star[:,-1] = uu_star[:,-2]        # for plotting purposes

    # Plots

    plt.figure('descent direction')
    plt.plot(np.arange(max_iters), descent[:max_iters])
    plt.xlabel('$k$')
    plt.ylabel('||$\\nabla J(\\mathbf{u}^k)||$')
    plt.yscale('log')
    plt.grid()
    plt.show(block=False)

    plt.figure('cost')
    plt.plot(np.arange(max_iters), JJ[:max_iters])
    plt.xlabel('$k$')
    plt.ylabel('$J(\\mathbf{u}^k)$')
    plt.yscale('log')
    plt.grid()
    plt.show(block=False)

# Design OPTIMAL TRAJECTORY  ---------------------------------------------------------------------------------------
if plot:
    fig, axs = plt.subplots(ns+ni, 1, sharex='all')

    axs[0].plot(tt_hor, xx_star[0,:], linewidth=2)
    axs[0].plot(tt_hor, xx_ref[0,:], 'g--', linewidth=2)
    axs[0].grid()
    axs[0].set_ylabel('$x$')

    axs[1].plot(tt_hor, xx_star[1,:], linewidth=2)
    axs[1].plot(tt_hor, xx_ref[1,:], 'g--', linewidth=2)
    axs[1].grid()
    axs[1].set_ylabel('$y$')

    axs[2].plot(tt_hor, xx_star[2,:],'r', linewidth=2)
    axs[2].plot(tt_hor, xx_ref[2,:], 'r--', linewidth=2)
    axs[2].grid()
    axs[2].set_ylabel('$psi$')

    axs[3].plot(tt_hor, xx_star[3,:], linewidth=2)
    axs[3].plot(tt_hor, xx_ref[3,:], 'g--', linewidth=2)
    axs[3].grid()
    axs[3].set_ylabel('$V$')

    axs[4].plot(tt_hor, xx_star[4,:], linewidth=2)
    axs[4].plot(tt_hor, xx_ref[4,:], 'g--', linewidth=2)
    axs[4].grid()
    axs[4].set_ylabel('$beta$')

    axs[5].plot(tt_hor, xx_star[5,:],'r', linewidth=2)
    axs[5].plot(tt_hor, xx_ref[5,:], 'r--', linewidth=2)
    axs[5].grid()
    axs[5].set_ylabel('$psi dot$')

    axs[6].plot(tt_hor, uu_star[0,:], linewidth=2)
    axs[6].plot(tt_hor, uu_ref[0,:], 'g--', linewidth=2)
    axs[6].grid()
    axs[6].set_ylabel('$delta$')

    axs[7].plot(tt_hor, uu_star[1,:],'r', linewidth=2)
    axs[7].plot(tt_hor, uu_ref[1,:], 'r--', linewidth=2)
    axs[7].grid()
    axs[7].set_ylabel('$F$')
    axs[7].set_xlabel('time')

    plt.show()

    # Plotting the trajectory
    plt.plot(xx_star[0,:], xx_star[1,:], label='Trajectory')
    plt.title('Vehicle Trajectory')
    plt.xlabel('X-axis')
    plt.ylabel('Y-axis')
    plt.legend()
    plt.grid(True)
    plt.show()

#########################################
### TASK 2: TRAJECTORY GENERATION II ####
#########################################

# SMOOTHING the reference trajectory  -----------------------------------------------------------------------------------

# Perform linear interpolation for reference trajectory
fig, axs = plt.subplots(8, 1, sharex='all')
fig.suptitle('Trajectory Smoothing using PCHIP Spline')
traj_smooth = np.zeros((8,T))
x_traj_smooth = np.zeros((8,T))

axs[0].plot(tt_hor, traj_ref[0, :], 'g--', linewidth=2, label='Original Reference Trajectory')
axs[0].grid()
axs[1].plot(tt_hor, traj_ref[1, :], 'g--', linewidth=2, label='Original Reference Trajectory')
axs[1].grid()
axs[2].plot(tt_hor, traj_ref[2, :], 'g--', linewidth=2, label='Original Reference Trajectory')
axs[2].grid()

for i in range (3,ns+ni):
    new_num_points = 7      # Adjust the number of points for a smoother curve
    interp_indices = np.linspace(0, T - 1, new_num_points)
    new_traj_ref_0 = np.interp(interp_indices, tt_hor, traj_ref[i,:])

    # define point to create spline
    x_spl = np.array([interp_indices[0], interp_indices[1], interp_indices[2], interp_indices[4], interp_indices[5], interp_indices[6]])
    y_spl = np.array([new_traj_ref_0[0], new_traj_ref_0[1], new_traj_ref_0[2], new_traj_ref_0[4], new_traj_ref_0[5], new_traj_ref_0[6]])

    # Create a piecewise cubic Hermite interpolating polynomial(PCHIP) interpolation of the given points
    cs = PchipInterpolator(x_spl, y_spl)

    # Generate new, smoother x values (denser for plotting)
    x_spl_new = np.linspace(min(x_spl), max(x_spl), T)

    # Compute the smoothed y values
    y_spl_new = cs(x_spl_new)

    # Store the values inside an array
    traj_smooth[i,:] = y_spl_new

    # Plotting the original and smoothed trajectories
    axs[i].plot(tt_hor, traj_ref[i, :], 'g--', linewidth=2, label='Original Reference Trajectory')
    axs[i].plot(interp_indices, new_traj_ref_0, 'b--', linewidth=2, label='Interpolated Trajectory')
    axs[i].plot(x_spl, y_spl, 'o', label='Points used for spline creation')
    axs[i].plot(x_spl_new, y_spl_new, 'r-', label='Smoothed Trajectory')
    axs[i].grid()
    if i == 8:
        axs[i].xlabel('time')

axs[0].set_ylabel('$x$')
axs[1].set_ylabel('$y$')
axs[2].set_ylabel('$psi$')
axs[3].set_ylabel('$V$')
axs[4].set_ylabel('$beta$')
axs[5].set_ylabel('$psi dot$')
axs[6].set_ylabel('$delta$')
axs[7].set_ylabel('$F$')
plt.legend()
plt.show()

# NEWTON'S METHOD evaluation  ----------------------------------------------------------------------------------------
# arrays to store data
xx = np.zeros((ns, T, max_iters))   # state seq.
uu = np.zeros((ni, T, max_iters))   # input seq.

xx_ref = traj_smooth[0:6,:]
uu_ref = traj_smooth[6:,:]

xx, uu, descent, JJ = nwtn.Newton(xx_ref, uu_ref, max_iters)

xx_star = xx[:,:,max_iters-1]
uu_star = uu[:,:,max_iters-1]
uu_star[:,-1] = uu_star[:,-2]        # for plotting purposes

# Plots

plt.figure('descent direction')
plt.plot(np.arange(max_iters), descent[:max_iters])
plt.xlabel('$k$')
plt.ylabel('||$\\nabla J(\\mathbf{u}^k)||$')
plt.yscale('log')
plt.grid()
plt.show(block=False)

plt.figure('cost')
plt.plot(np.arange(max_iters), JJ[:max_iters])
plt.xlabel('$k$')
plt.ylabel('$J(\\mathbf{u}^k)$')
plt.yscale('log')
plt.grid()
plt.show(block=False)

# Design OPTIMAL TRAJECTORY  ---------------------------------------------------------------------------------------

fig, axs = plt.subplots(ns+ni, 1, sharex='all')

axs[0].plot(tt_hor, xx_star[0,:], linewidth=2)
axs[0].plot(tt_hor, xx_ref[0,:], 'g--', linewidth=2)
axs[0].grid()
axs[0].set_ylabel('$x$')

axs[1].plot(tt_hor, xx_star[1,:], linewidth=2)
axs[1].plot(tt_hor, xx_ref[1,:], 'g--', linewidth=2)
axs[1].grid()
axs[1].set_ylabel('$y$')

axs[2].plot(tt_hor, xx_star[2,:],'r', linewidth=2)
axs[2].plot(tt_hor, xx_ref[2,:], 'r--', linewidth=2)
axs[2].grid()
axs[2].set_ylabel('$psi$')

axs[3].plot(tt_hor, xx_star[3,:], linewidth=2)
axs[3].plot(tt_hor, xx_ref[3,:], 'g--', linewidth=2)
axs[3].grid()
axs[3].set_ylabel('$V$')

axs[4].plot(tt_hor, xx_star[4,:], linewidth=2)
axs[4].plot(tt_hor, xx_ref[4,:], 'g--', linewidth=2)
axs[4].grid()
axs[4].set_ylabel('$beta$')

axs[5].plot(tt_hor, xx_star[5,:],'r', linewidth=2)
axs[5].plot(tt_hor, xx_ref[5,:], 'r--', linewidth=2)
axs[5].grid()
axs[5].set_ylabel('$psi dot$')

axs[6].plot(tt_hor, uu_star[0,:], linewidth=2)
axs[6].plot(tt_hor, uu_ref[0,:], 'g--', linewidth=2)
axs[6].grid()
axs[6].set_ylabel('$delta$')

axs[7].plot(tt_hor, uu_star[1,:],'r', linewidth=2)
axs[7].plot(tt_hor, uu_ref[1,:], 'r--', linewidth=2)
axs[7].grid()
axs[7].set_ylabel('$F$')
axs[7].set_xlabel('time')

plt.show()

# Plotting the trajectory
plt.plot(xx_star[0,:], xx_star[1,:], label='Trajectory')
plt.title('Vehicle Trajectory')
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.legend()
plt.grid(True)
plt.show()


#########################################
##### TASK 3: TRAJECTORY VIA LQR ########
#########################################

A_opt = np.zeros((ns, ns, T))
B_opt = np.zeros((ns, ni, T))
Qt_reg = np.zeros((ns, ns, T))
Rt_reg = np.zeros((ni, ni, T))

for tt in range (T):
    fx, fu = dyn.dynamics(xx_star[:,tt], uu_star[:,tt])[1:]

    A_opt[:,:,tt] = fx.T
    B_opt[:,:,tt] = fu.T

    Qt_reg[:,:,tt] = 0.1*np.diag([1, 1, 100, 1, 100, 100])
    Rt_reg[:,:,tt] = 0.01*np.diag([100, 1])

QT_reg = Qt_reg[:,:,T]

def lti_LQR(AA, BB, QQ, RR, QQf, T):

    """
        LQR for LTI system with fixed cost	
        
    Args
        - AA (nn x nn) matrix
        - BB (nn x mm) matrix
        - QQ (nn x nn), RR (mm x mm) stage cost
        - QQf (nn x nn) terminal cost
        - TT time horizon
    Return
        - KK (mm x nn x TT) optimal gain sequence
        - PP (nn x nn x TT) riccati matrix
    """
        
    ns = AA.shape[1]
    ni = BB.shape[1]

    
    PP = np.zeros((ns,ns,TT))
    KK = np.zeros((ni,ns,TT))
    
    PP[:,:,-1] = QQf
    
    # Solve Riccati equation
    for tt in reversed(range(TT-1)):
        QQt = QQ
        RRt = RR
        AAt = AA
        BBt = BB
        PPtp = PP[:,:,tt+1]
        
        PP[:,:,tt] = QQt + AAt.T@PPtp@AAt - (AAt.T@PPtp@BBt)@np.linalg.inv((RRt + BBt.T@PPtp@BBt))@(BBt.T@PPtp@AAt)
    
    # Evaluate KK
    
    
    for tt in range(TT-1):
        QQt = QQ
        RRt = RR
        AAt = AA
        BBt = BB
        PPtp = PP[:,:,tt+1]
        
        KK[:,:,tt] = -np.linalg.inv(RRt + BBt.T@PPtp@BBt)@(BBt.T@PPtp@AAt)

    return KK
    
KK_reg = lti_LQR(A_opt, B_opt, Qt_reg, Rt_reg, QT_reg, T)

xx_temp = np.zeros((ns,T))
uu_temp = np.zeros((ni,T))

xx_temp[:,0] = np.array((0,0,0,1,0,0))      # initial conditions different from the ones of xx0_star 

for tt in range(T-1):
    uu_temp[:,tt] = uu_star[:,tt] + KK_reg[:,:,tt]@(xx_temp[:,tt]-xx_star[:,tt])
    xx_temp[:,tt+1] = dyn.dynamics(xx_temp[:,tt], uu_temp[:,tt])[0]

uu_reg = uu_temp
xx_reg = xx_temp


# Design REGULARIZED TRAJECTORY  ---------------------------------------------------------------------------------------

fig, axs = plt.subplots(ns+ni, 1, sharex='all')

axs[0].plot(tt_hor, xx_reg[0,:], linewidth=2)
axs[0].plot(tt_hor, xx_star[0,:], 'g--', linewidth=2)
axs[0].grid()
axs[0].set_ylabel('$x$')

axs[1].plot(tt_hor, xx_reg[1,:], linewidth=2)
axs[1].plot(tt_hor, xx_star[1,:], 'g--', linewidth=2)
axs[1].grid()
axs[1].set_ylabel('$y$')

axs[2].plot(tt_hor, xx_reg[2,:],'r', linewidth=2)
axs[2].plot(tt_hor, xx_star[2,:], 'r--', linewidth=2)
axs[2].grid()
axs[2].set_ylabel('$psi$')

axs[3].plot(tt_hor, xx_reg[3,:], linewidth=2)
axs[3].plot(tt_hor, xx_star[3,:], 'g--', linewidth=2)
axs[3].grid()
axs[3].set_ylabel('$V$')

axs[4].plot(tt_hor, xx_reg[4,:], linewidth=2)
axs[4].plot(tt_hor, xx_star[4,:], 'g--', linewidth=2)
axs[4].grid()
axs[4].set_ylabel('$beta$')

axs[5].plot(tt_hor, xx_reg[5,:],'r', linewidth=2)
axs[5].plot(tt_hor, xx_star[5,:], 'r--', linewidth=2)
axs[5].grid()
axs[5].set_ylabel('$psi dot$')

axs[6].plot(tt_hor, uu_reg[0,:], linewidth=2)
axs[6].plot(tt_hor, uu_star[0,:], 'g--', linewidth=2)
axs[6].grid()
axs[6].set_ylabel('$delta$')

axs[7].plot(tt_hor, uu_reg[1,:],'r', linewidth=2)
axs[7].plot(tt_hor, uu_star[1,:], 'r--', linewidth=2)
axs[7].grid()
axs[7].set_ylabel('$F$')
axs[7].set_xlabel('time')

plt.show()

# Plotting the trajectory
plt.plot(xx_reg[0,:], xx_reg[1,:], label='Trajectory')
plt.title('Vehicle Trajectory')
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.legend()
plt.grid(True)
plt.show()

#########################################
##### TASK 4: TRAJECTORY VIA LQR ########
#########################################
