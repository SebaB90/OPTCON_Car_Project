#
# Optimal Control of a vehicle
# Main
# Antonio Rapallini & Sebastiano Bertamé
# Bologna, 04/01/2024
#

import numpy as np
import scipy as sp
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.ticker import (AutoMinorLocator, MultipleLocator) 
from scipy.optimize import fsolve
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator
import cvxpy as cp
import sys
import Dynamics as dyn
import Costs as cst
import Newton as nwtn
import Gradient as grad 

# Allow Ctrl-C to work despite plotting
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

test = False # Set true for testing the open loop dynamics and the correctness of the derivatives
visu_animation = True

#######################################################################
###################### TASK 0: DISCRETIZATION #########################
#######################################################################

############################################################
# Trajectory parameters
############################################################

tf = dyn.tf  # Final time in seconds

dt = dyn.dt  # Get discretization step from dynamics
ns = dyn.ns  # Get the number of states from the dynamics
ni = dyn.ni  # Get the number of input from the dynamics

TT = dyn.TT  # Number of discrete-time samples
TT_mid = dyn.TT_mid

max_iters = 15

############################################################
# TESTS
############################################################

if test == True and ns==6:
    
    ######################################
    # OPEN LOOP TEST TO CHECK IF THE VEHICLE DYNAMICS IS CORRECT
    ######################################

    # Defining an x and a u
    uu = np.array([0.25, 20])
    xx = np.array([0, 0, 0, 1, 0, 0])

    # Variables for evaluating the dynamics in time
    x_traj = [np.copy(xx[0])]
    y_traj = [np.copy(xx[1])]
    traj = np.copy(xx)

    total_time = 100  # Adjust the total simulation time as needed
    num_steps = int(total_time / dt)

    for i in range(num_steps-1):
        traj = dyn.dynamics(traj, uu)[0]
        x_traj.append(traj[0])
        y_traj.append(traj[1])

    # Plotting the obtained trajectory
    fig, axs = plt.subplots(2, 1, sharex='all')

    axs[0].plot(np.linspace(0, TT, num_steps), x_traj, 'g', linewidth=2)
    axs[0].grid()
    axs[0].set_ylabel('$x$')
    axs[0].set_title('X Trajectory')  # Add a title to the first subplot


    axs[1].plot(np.linspace(0, TT, num_steps), y_traj, 'g', linewidth=2)
    axs[1].grid()
    axs[1].set_ylabel('$y$')
    axs[1].set_xlabel('time')
    axs[1].set_title('Y Trajectory')  # Add a title to the first subplot


    fig.align_ylabels(axs)
    plt.show()

    # Plot of the x-y trajectory
    plt.plot(x_traj, y_traj, 'g', linewidth=2)
    plt.title('Vehicle Trajectory')
    plt.xlabel('X-axis')
    plt.ylabel('Y-axis')
    plt.grid(True)
    plt.show()

    ######################################
    # CHECK OF THE DERIVATIVES
    ######################################
    '''
    As simple test we check if:
        f(x_bar + dltx) - f(x_bar) = df/dx(evaluated in x_bar) * dltx
    '''

    # Define the infinitesimal increments for evaluating the derivatives
    dx = 1e-3 
    du = 1e-3       
    
    # Evaluated the derivatives from the dynamics
    xxp, fx, fu = dyn.dynamics(xx, uu)
    
    # Evaluate the A and B matrices
    AA = fx.T
    BB = fu.T
    
    # Arrays to store data
    xdx = np.zeros((ns,))
    dltx = np.random.normal(0,0.001,ns)
    udu = np.zeros((ni,))
    dltu = np.random.normal(0,0.001,ni)
    
    for i in range (0,ns):
        dltx[i] = dx

    for i in range (0,ni):
        dltu[i] = du

    xdx = xx + dltx
    xx_plus = dyn.dynamics(xdx, uu)[0]
    diff_x = xx_plus - xxp
    check_x = diff_x - AA@dltx

    udu = uu + dltu
    xx_plus = dyn.dynamics(xx, udu)[0]    
    diff_u = xx_plus - xxp     
    check_u = diff_u - BB@dltu

    print("\n\n")
    blue_bold_title = "\033[1;34mERROR IN THE EVALUATED DERIVATIVES:\033[0m"
    print(blue_bold_title)
    print(f'\nError in derivatives of x is:\n{check_x}')
    print(f'\nError in derivatives of u is:\n{check_u}\n')


########################################################################
############## TASK 1: TRAJECTORY GENERATION (I) #######################
########################################################################

if ns == 6:
    
  # Import of the parameters of the system
  mm = dyn.mm  # Kg
  Iz = dyn.Iz  # Kg*m^2
  aa = dyn.aa  # m           
  bb = dyn.bb  # m
  mi = dyn.mi  # nodim
  gg = dyn.gg  # m/s^2

  eq = np.zeros((ns+ni, 2))
  xx_eq = np.zeros((ns,2))
  uu_eq = np.zeros((ni,2))


  ############################################################
  # Evalutaion of two equilibria for the system
  ############################################################
  
  # We have evaluated the cornering equilibria, so setting Betadot = 0, Vdot = 0 and Psidotdot = 0
  # Then imposing V(x3) and Beta(x4) we evaluate the other states and inputs

  def equations(vars):

    Beta = [vars[1] - (x3*np.sin(x4) + aa*vars[0])/(x3*np.cos(x4)), - (x3*np.sin(x4) - bb*vars[0])/(x3*np.cos(x4))]               # Beta = [Beta_f, Beta_r]
    Fz = [mm*gg*bb/(aa+bb), mm*gg*aa/(aa+bb)]                                                                         # Fz = [F_zf, F_zr]
    Fy = [mi*Fz[0]*Beta[0], mi*Fz[1]*Beta[1]]                                                                         # Fy = [F_yf, F_yr]

    return [((Fy[1] * np.sin(x4) + vars[2] * np.cos(x4 - vars[1]) + Fy[0] * np.sin(x4 - vars[1]))/mm), 
            (Fy[1] * np.cos(x4) + Fy[0] * np.cos(x4 - vars[1]) - vars[2] * np.sin(x4 - vars[1]))/(mm * x3) - vars[0], 
            ((vars[2] * np.sin(vars[1]) + Fy[0] * np.cos(vars[1])) * aa - Fy[1] * bb)/Iz]

  # Initial guess for the fsolve evaluation
  initial_guess = [0.1, 0.1, 5]  # [x5(0), u0(0), u1(0)]

  #######################
  # FIRST EQUILIBRIUM
  #######################

  # Imposing x3 and x4 we evaluate the other parameters
  x3 = 3                  
  x4 = 0.02

  eq[3,0] = np.copy(x3)                           # V
  eq[4,0] = np.copy(x4)                           # beta
  eq[5:,0] = fsolve(equations, [0.1, 0.1, 5])     # psi dot, steering angle, force
  eq[2,0] = eq[5,0]*int(tf/2)                               # psi   
  eq[0,0] =(eq[3,0]*np.cos(eq[4,0])*np.cos(eq[2,0])-eq[3,0]*np.sin(eq[4,0])*np.sin(eq[2,0]))*int(tf/2)     # x
  eq[1,0] =(eq[3,0]*np.cos(eq[4,0])*np.sin(eq[2,0])+eq[3,0]*np.sin(eq[4,0])*np.cos(eq[2,0]))*int(tf/2)     # y

  #######################
  # SECOND EQUILIBRIUM
  #######################
  x3 = 5
  x4 = 0.07

  eq[3,1] = np.copy(x3)                           # V
  eq[4,1] = np.copy(x4)                           # beta
  eq[5:,1] = fsolve(equations, [0.1, 0.1, 5])     # psi dot, steering angle, force
  eq[2,1] = eq[2,0] + eq[5,1]*int(tf/2)                               # psi   
  eq[0,1] = eq[0,0] + (eq[3,1]*np.cos(eq[4,1])*np.cos(eq[2,1])-eq[3,1]*np.sin(eq[4,1])*np.sin(eq[2,1]))*int(tf/2)     # x
  eq[1,1] = eq[1,0] + (eq[3,1]*np.cos(eq[4,1])*np.sin(eq[2,1])+eq[3,1]*np.sin(eq[4,1])*np.cos(eq[2,1]))*int(tf/2)     # y

  xx_eq = eq[:ns,:]
  uu_eq = eq[ns:,:]

  # Print the result
  print("\n\n")
  blue_bold_title = "\033[1;34mEVALUATED EQUILIBRIUM:\033[0m"
  print(blue_bold_title)
  print(f" \nxx at Equilibrium 1:\n  {xx_eq[0:, 0]}")
  print(f" \nuu at Equilibrium 1:\n  {uu_eq[0:, 0]}")
  print(f" \nxx at Equilibrium 2:\n  {xx_eq[0:, 1]}")
  print(f" \nuu at Equilibrium 2:\n  {uu_eq[0:, 1]}\n\n")
  
  
  ############################################################
  # Evalutaion of the reference trajectory
  ############################################################

  traj_ref = np.zeros((ns+ni, TT))
  traj_ref[3:,0] = eq[3:,0]

  # Step reference signal - for all the states

  for tt in range(1,TT):

    traj = dyn.dynamics(traj_ref[:6,tt-1], traj_ref[6:,tt-1])[0]
    traj_ref[:3, tt] = traj[:3]     # used to update x, y, psi

    if tt < TT_mid:
      traj_ref[3:, tt] = eq[3:,0]

    else:  
      traj_ref[3:, tt] = eq[3:,1]


  xx_ref = traj_ref[0:6,:]
  uu_ref = traj_ref[6:,:]


  # Plot of the reference trajcetory
  tt_hor = np.linspace(0,tf,TT)

  # Plot to test trajectory reference
  plt.plot(traj_ref[0,:], traj_ref[1,:], label='Trajectory')
  plt.title('Vehicle Reference Trajectory')
  plt.xlabel('X-axis')
  plt.ylabel('Y-axis')
  plt.grid(True)
  plt.show()

  fig, axs = plt.subplots(ns+ni, 1, sharex='all')

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

  fig.suptitle("Reference", fontsize=16)
  fig.align_ylabels(axs)

  plt.show()
    
    

if ns == 2:
  ######################################
  # Reference curve for the pendulum
  ######################################
  ref_deg_0 = 0
  ref_deg_T = 30

  xx_ref = np.zeros((ns, TT))
  uu_ref = np.zeros((ni, TT))

  # Step reference
  KKeq = dyn.KKeq
  xx_ref[0, int(TT/2):] = np.ones((1, int(TT/2))) * np.deg2rad(ref_deg_T)
  uu_ref[0, :] = KKeq * np.sin(xx_ref[0, :])

  x0 = xx_ref[:, 0]
  
  # Plot of the reference trajcetory
  tt_hor = np.linspace(0,tf,TT)

  fig, axs = plt.subplots(ns+ni, 1, sharex='all')

  axs[0].plot(tt_hor, xx_ref[0,:], 'g--', linewidth=2)
  axs[0].grid()
  axs[0].set_ylabel('$x_1$')

  axs[1].plot(tt_hor, xx_ref[1,:], 'g--', linewidth=2)
  axs[1].grid()
  axs[1].set_ylabel('$x_2$')

  axs[2].plot(tt_hor, uu_ref[0,:], 'r--', linewidth=2)
  axs[2].grid()
  axs[2].set_ylabel('$u$')
  axs[2].set_xlabel('time')

  plt.show()


#####################################################################
# NEWTON'S METHOD evaluation  
####################################################################

xx = np.zeros((ns, TT, max_iters+1))   # state seq.
uu = np.zeros((ni, TT, max_iters+1))   # input seq.

# initial conditions
if ns == 6:
  for tt in range(TT):
    xx[:,tt,0] = np.copy(xx_ref[:,0])
    uu[:,tt,0] = np.copy(uu_ref[:,0]) 

x0 = np.copy(xx_ref[:,0])
# xx, uu, descent, JJ, kk = grad.Gradient(xx, uu, xx_ref, uu_ref, cst.QQt, cst.RRt, cst.QQT, max_iters)
xx, uu, descent, JJ, kk = nwtn.Newton(xx, uu, xx_ref, uu_ref, x0, max_iters)

xx_star = xx[:,:,kk]
uu_star = uu[:,:,kk]
uu_star[:,-1] = uu_star[:,-3]        # for plotting purposes

# Plots

plt.figure('descent direction')
plt.plot(np.arange(kk), descent[:kk])
plt.xlabel('$k$')
plt.ylabel('||$\\nabla J(\\mathbf{u}^k)||$')
plt.yscale('log')
plt.grid()
plt.show(block=False)

plt.figure('cost')
plt.plot(np.arange(kk), JJ[:kk])
plt.xlabel('$k$')
plt.ylabel('$J(\\mathbf{u}^k)$')
plt.yscale('log')
plt.grid()
plt.show(block=False)

##############################################################
# Design OPTIMAL TRAJECTORY  
##############################################################

fig, axs = plt.subplots(ns+ni, 1, sharex='all')

if ns == 6:
  axs[0].plot(tt_hor, xx_star[0,:], linewidth=2)
  axs[0].plot(tt_hor, xx_ref[0,:], 'g--', linewidth=2)
  axs[0].grid()
  axs[0].set_ylabel('$x$')

  axs[1].plot(tt_hor, xx_star[1,:], linewidth=2)
  axs[1].plot(tt_hor, xx_ref[1,:], 'g--', linewidth=2)
  axs[1].grid()
  axs[1].set_ylabel('$y$')

  axs[2].plot(tt_hor, xx_star[2,:], linewidth=2)
  axs[2].plot(tt_hor, xx_ref[2,:], 'g--', linewidth=2)
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

  axs[5].plot(tt_hor, xx_star[5,:], linewidth=2)
  axs[5].plot(tt_hor, xx_ref[5,:], 'g--', linewidth=2)
  axs[5].grid()
  axs[5].set_ylabel('$psi dot$')

  axs[6].plot(tt_hor, uu_star[0,:],'r', linewidth=2)
  axs[6].plot(tt_hor, uu_ref[0,:], 'g--', linewidth=2)
  axs[6].grid()
  axs[6].set_ylabel('$delta$')

  axs[7].plot(tt_hor, uu_star[1,:],'r', linewidth=2)
  axs[7].plot(tt_hor, uu_ref[1,:], 'g--', linewidth=2)
  axs[7].grid()
  axs[7].set_ylabel('$F$')
  axs[7].set_xlabel('time')

if ns == 2:
  axs[0].plot(tt_hor, xx_star[0,:], linewidth=2)
  axs[0].plot(tt_hor, xx_ref[0,:], 'g--', linewidth=2)
  axs[0].grid()
  axs[0].set_ylabel('$x_1$')

  axs[1].plot(tt_hor, xx_star[1,:], linewidth=2)
  axs[1].plot(tt_hor, xx_ref[1,:], 'g--', linewidth=2)
  axs[1].grid()
  axs[1].set_ylabel('$x_2$')

  axs[2].plot(tt_hor, uu_star[0,:],'r', linewidth=2)
  axs[2].plot(tt_hor, uu_ref[0,:], 'r--', linewidth=2)
  axs[2].grid()
  axs[2].set_ylabel('$u$')
  axs[2].set_xlabel('time')
    
plt.show()

# Plotting the trajectory
plt.plot(xx_star[0,:], xx_star[1,:], label='Optimal Trajectory')
plt.plot(xx_ref[0,:], xx_ref[1,:],'r--', label='Reference Trajectory')
plt.title('Vehicle Trajectory')
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.legend()
plt.grid(True)
plt.show()

# stop the simulation for the pendulum
if ns == 2:
  print("\n\n")
  purple_bold_title = "\033[1;35mPENDULUM EVALUATION TERMINATED\033[0m"
  print(purple_bold_title) 
  print("\n\n")
  sys.exit()

########################################################################
############## TASK 2: TRAJECTORY GENERATION (II) ######################
########################################################################

############################################################
# SMOOTHING the reference trajectory
############################################################

# Perform linear interpolation for reference trajectory
fig, axs = plt.subplots(ns+ni, 1, sharex='all')
fig.suptitle('Trajectory Smoothing using PCHIP Spline')
traj_smooth = np.zeros((ns+ni,TT))
x_traj_smooth = np.zeros((ns+ni,TT))

axs[0].plot(tt_hor, traj_ref[0, :], 'g--', linewidth=2, label='Original Reference Trajectory')
axs[0].grid()
axs[1].plot(tt_hor, traj_ref[1, :], 'g--', linewidth=2, label='Original Reference Trajectory')
axs[1].grid()
axs[2].plot(tt_hor, traj_ref[2, :], 'g--', linewidth=2, label='Original Reference Trajectory')
axs[2].grid()

traj_smooth[:3,:] = traj_ref[:3,:]

for i in range (3,ns+ni):
  new_num_points = 7      # Adjust the number of points for a smoother curve
  interp_indices = np.linspace(0, tf, new_num_points)
  new_traj_ref_0 = np.interp(interp_indices, tt_hor, traj_ref[i,:])

  # define point to create spline
  x_spl = np.array([interp_indices[0], interp_indices[1], interp_indices[2], interp_indices[4], interp_indices[5], interp_indices[6]])
  y_spl = np.array([new_traj_ref_0[0], new_traj_ref_0[1], new_traj_ref_0[2], new_traj_ref_0[4], new_traj_ref_0[5], new_traj_ref_0[6]])

  # Create a piecewise cubic Hermite interpolating polynomial(PCHIP) interpolation of the given points
  cs = PchipInterpolator(x_spl, y_spl)

  # Generate new, smoother x values (denser for plotting)
  x_spl_new = np.linspace(min(x_spl), max(x_spl), TT)

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
  if i == ns+ni:
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


#####################################################################
# NEWTON'S METHOD evaluation  
#####################################################################

# arrays to store data
xx = np.zeros((ns, TT, max_iters+1))   # state seq.
uu = np.zeros((ni, TT, max_iters+1))   # input seq.

xx_ref = traj_smooth[0:6,:]
uu_ref = traj_smooth[6:,:]

# initial conditions
if ns == 6:
  for tt in range(TT):
    xx[:,tt,0] = np.copy(xx_ref[:,0]) 
    uu[:,tt,0] = np.copy(uu_ref[:,0])

x0 = np.copy(xx_ref[:,0])

xx, uu, descent, JJ, kk = nwtn.Newton(xx, uu, xx_ref, uu_ref, x0, max_iters)

xx_star = xx[:,:,kk-1]
uu_star = uu[:,:,kk-1]
uu_star[:,-1] = uu_star[:,-2]        # for plotting purposes

# Plots

plt.figure('descent direction')
plt.plot(np.arange(kk), descent[:kk])
plt.xlabel('$k$')
plt.ylabel('||$\\nabla J(\\mathbf{u}^k)||$')
plt.yscale('log')
plt.grid()
plt.show(block=False)

plt.figure('cost')
plt.plot(np.arange(kk), JJ[:kk])
plt.xlabel('$k$')
plt.ylabel('$J(\\mathbf{u}^k)$')
plt.yscale('log')
plt.grid()
plt.show(block=False)

##############################################################
# Design OPTIMAL TRAJECTORY  
##############################################################

fig, axs = plt.subplots(ns+ni, 1, sharex='all')

axs[0].plot(tt_hor, xx_star[0,:], linewidth=2)
axs[0].plot(tt_hor, xx_ref[0,:], 'g--', linewidth=2)
axs[0].grid()
axs[0].set_ylabel('$x$')

axs[1].plot(tt_hor, xx_star[1,:], linewidth=2)
axs[1].plot(tt_hor, xx_ref[1,:], 'g--', linewidth=2)
axs[1].grid()
axs[1].set_ylabel('$y$')

axs[2].plot(tt_hor, xx_star[2,:], linewidth=2)
axs[2].plot(tt_hor, xx_ref[2,:], 'g--', linewidth=2)
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

axs[5].plot(tt_hor, xx_star[5,:], linewidth=2)
axs[5].plot(tt_hor, xx_ref[5,:], 'g--', linewidth=2)
axs[5].grid()
axs[5].set_ylabel('$psi dot$')

axs[6].plot(tt_hor, uu_star[0,:], 'r', linewidth=2)
axs[6].plot(tt_hor, uu_ref[0,:], 'g--', linewidth=2)
axs[6].grid()
axs[6].set_ylabel('$delta$')

axs[7].plot(tt_hor, uu_star[1,:],'r', linewidth=2)
axs[7].plot(tt_hor, uu_ref[1,:], 'g--', linewidth=2)
axs[7].grid()
axs[7].set_ylabel('$F$')
axs[7].set_xlabel('time')

plt.show()

# Plotting the trajectory
plt.plot(xx_star[0,:], xx_star[1,:], label='Optimal Trajectory')
plt.plot(xx_ref[0,:], xx_ref[1,:],'r--', label='Reference Trajectory')
plt.title('Vehicle Trajectory')
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.legend()
plt.grid(True)
plt.show()

#######################################################################
############### TASK 3: TRAJECTORY TRACKING VIA LQR ###################
#######################################################################

A_opt = np.zeros((ns, ns, TT))
B_opt = np.zeros((ns, ni, TT))
Qt_reg = np.zeros((ns, ns, TT))
Rt_reg = np.zeros((ni, ni, TT))

for tt in range (TT):
  fx, fu = dyn.dynamics(xx_star[:,tt], uu_star[:,tt])[1:]

  A_opt[:,:,tt] = fx.T
  B_opt[:,:,tt] = fu.T

  Qt_reg[:,:,tt] = cst.QQt
  Rt_reg[:,:,tt] = cst.RRt

QT_reg = cst.QQT


def lti_LQR(AA, BB, QQ, RR, QQf, TT):

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
    QQt = QQ[:,:,tt]
    RRt = RR[:,:,tt]
    AAt = AA[:,:,tt]
    BBt = BB[:,:,tt]
    PPtp = PP[:,:,tt+1]
    
    PP[:,:,tt] = QQt + AAt.T@PPtp@AAt - (AAt.T@PPtp@BBt)@np.linalg.inv((RRt + BBt.T@PPtp@BBt))@(BBt.T@PPtp@AAt)
  
  # Evaluate KK
  for tt in range(TT-1):
    QQt = QQ[:,:,tt]
    RRt = RR[:,:,tt]
    AAt = AA[:,:,tt]
    BBt = BB[:,:,tt]
    PPtp = PP[:,:,tt+1]
    
    KK[:,:,tt] = -np.linalg.inv(RRt + BBt.T@PPtp@BBt)@(BBt.T@PPtp@AAt)

  return KK
    
KK_reg = lti_LQR(A_opt, B_opt, Qt_reg, Rt_reg, QT_reg, TT)

xx_temp = np.zeros((ns,TT))
uu_temp = np.zeros((ni,TT))

xx_temp[:,0] = np.array((0,0,0,2,0.3,0.01))      # initial conditions different from the ones of xx0_star 

for tt in range(TT-1):
  uu_temp[:,tt] = uu_star[:,tt] + KK_reg[:,:,tt]@(xx_temp[:,tt]-xx_star[:,tt])
  xx_temp[:,tt+1] = dyn.dynamics(xx_temp[:,tt], uu_temp[:,tt])[0]

uu_reg = uu_temp
xx_reg = xx_temp

##############################################################
# Design REGULARIZED TRAJECTORY  
##############################################################

fig, axs = plt.subplots(ns+ni, 1, sharex='all')

axs[0].plot(tt_hor, xx_reg[0,:], linewidth=2)
axs[0].plot(tt_hor, xx_star[0,:], 'g--', linewidth=2)
axs[0].grid()
axs[0].set_ylabel('$x$')

axs[1].plot(tt_hor, xx_reg[1,:], linewidth=2)
axs[1].plot(tt_hor, xx_star[1,:], 'g--', linewidth=2)
axs[1].grid()
axs[1].set_ylabel('$y$')

axs[2].plot(tt_hor, xx_reg[2,:], linewidth=2)
axs[2].plot(tt_hor, xx_star[2,:], 'g--', linewidth=2)
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

axs[5].plot(tt_hor, xx_reg[5,:], linewidth=2)
axs[5].plot(tt_hor, xx_star[5,:], 'g--', linewidth=2)
axs[5].grid()
axs[5].set_ylabel('$psi dot$')

axs[6].plot(tt_hor, uu_reg[0,:], 'r', linewidth=2)
axs[6].plot(tt_hor, uu_star[0,:], 'g--', linewidth=2)
axs[6].grid()
axs[6].set_ylabel('$delta$')

axs[7].plot(tt_hor, uu_reg[1,:],'r', linewidth=2)
axs[7].plot(tt_hor, uu_star[1,:], 'g--', linewidth=2)
axs[7].grid()
axs[7].set_ylabel('$F$')
axs[7].set_xlabel('time')

plt.show()

# Plotting the trajectory
plt.plot(xx_star[0,:], xx_star[1,:], label='Regularized Trajectory')
plt.plot(xx_reg[0,:], xx_reg[1,:],'r--', label='Optimal Trajectory')
plt.title('Vehicle Trajectory')
plt.xlabel('X-axis')
plt.ylabel('Y-axis')
plt.legend()
plt.grid(True)
plt.show()


#######################################################################
############## TASK 4: TRAJECTORY TRACKING VIA MPC ####################
#######################################################################
Tsim = TT

def linear_mpc(AA, BB, QQ, RR, QQf, xxt, umax, umin, xmax, xmin, T_pred):
  """
  Linear MPC solver - Constrained LQR

  Given a measured state xxt measured at t
  gives back the optimal input to be applied at t

  Args
  - AA, BB: linear dynamics
  - QQ,RR,QQf: cost matrices
  - xxt: initial condition (at time t)
  - T: time (prediction) horizon

  Returns
    - u_t: input to be applied at t
    - xx, uu predicted trajectory

  """

  xxt = xxt.squeeze()

  xx_mpc = cp.Variable((ns, T_pred))
  uu_mpc = cp.Variable((ni, T_pred))

  cost = 0
  constr = []

  for tt in range(T_pred-1):
    cost += cp.quad_form(xx_mpc[:,tt], QQ) + cp.quad_form(uu_mpc[:,tt], RR)
    constr += [xx_mpc[:,tt+1] == AA[:,:,tt]@xx_mpc[:,tt] + BB[:,:,tt]@uu_mpc[:,tt], # dynamics constraint
            uu_mpc[1,tt] >= umin,
            xx_mpc[4,tt] <= xmax]

  # sums problem objectives and concatenates constraints.
  cost += cp.quad_form(xx_mpc[:,T_pred-1], QQf)
  constr += [xx_mpc[:,0] == xxt]

  problem = cp.Problem(cp.Minimize(cost), constr)
  problem.solve()

  if problem.status == "infeasible":
  # Otherwise, problem.value is inf or -inf, respectively.
    print("Infeasible problem! CHECK YOUR CONSTRAINTS!!!")

  return uu_mpc[:,0].value, xx_mpc.value, uu_mpc.value

#############################
# Model Predictive Control
#############################

T_pred = 100       # MPC Prediction horizon
u1max = 600
u1min = 0

x4max = 0.15
x4min = 0

xx_real_mpc = np.zeros((ns,Tsim))
uu_real_mpc = np.zeros((ni,Tsim))

xx_mpc = np.zeros((ns, T_pred, Tsim))

xx_real_mpc[:,0] = xx_star[:,0]

for tt in range(Tsim-1):
  # System evolution - real with MPC

  xx_t_mpc = xx_real_mpc[:,tt] # get initial condition

  # Solve MPC problem - apply first input

  if tt%500 == 0: # print every 5 time instants
    print('MPC:\t t = {}'.format(tt*dt))

  uu_real_mpc[:,tt], xx_mpc[:,:,tt] = linear_mpc(A_opt, B_opt, cst.QQt, cst.RRt, cst.QQT, xx_t_mpc, umax=u1max, umin=u1min, xmax = x4max, xmin = x4min, T_pred = T_pred)[:2]
  
  xx_real_mpc[:,tt+1] = dyn.dynamics(xx_real_mpc[:,tt], uu_real_mpc[:,tt])[0]

#######################################
# Plots
#######################################

time = np.arange(Tsim)

fig, axs = plt.subplots(ns+ni, 1, sharex='all')

axs[0].plot(time, xx_real_mpc[0,:], linewidth=2)
axs[0].plot(time, xx_star[0,:],'--r', linewidth=2)
axs[0].grid()
axs[0].set_ylabel('$x$')
axs[0].set_xlim([-1,Tsim])
axs[0].legend(['MPC', 'OPT'])

#####
axs[1].plot(time, xx_real_mpc[1,:], linewidth=2)
axs[1].plot(time, xx_star[1,:], '--r', linewidth=2)
axs[1].grid()
axs[1].set_ylabel('$y$')
axs[1].set_xlim([-1,Tsim])
axs[1].legend(['MPC', 'OPT'])

#####
axs[2].plot(time, xx_real_mpc[2,:], linewidth=2)
axs[2].plot(time, xx_star[2,:], '--r', linewidth=2)
axs[2].grid()
axs[2].set_ylabel('$psi$')
axs[2].set_xlim([-1,Tsim])
axs[2].legend(['MPC', 'OPT'])

#####
axs[3].plot(time, xx_real_mpc[3,:], linewidth=2)
axs[3].plot(time, xx_star[3,:], '--r', linewidth=2)
axs[3].grid()
axs[3].set_ylabel('$V$')
axs[3].set_xlim([-1,Tsim])
axs[3].legend(['MPC', 'OPT'])

#####
axs[4].plot(time, xx_real_mpc[4,:], linewidth=2)
axs[4].plot(time, xx_star[4,:], '--r', linewidth=2)

if x4max < 1.1*np.amax(xx_real_mpc[4,:]): # draw constraints only if active
  axs[4].plot(time, np.ones(Tsim)*x4max, '--g', linewidth=1)
  axs[1].plot(time, np.ones(Tsim)*x4min, '--g', linewidth=1)

axs[4].grid()
axs[4].set_ylabel('$beta$')
axs[4].set_xlim([-1,Tsim])
axs[4].legend(['MPC', 'OPT'])

#####
axs[5].plot(time, xx_real_mpc[5,:], linewidth=2)
axs[5].plot(time, xx_star[5,:], '--r', linewidth=2)
axs[5].grid()
axs[5].set_ylabel('$psi dot$')
axs[5].set_xlim([-1,Tsim])
axs[5].legend(['MPC', 'OPT'])

#####
axs[6].plot(time, uu_real_mpc[0,:],'g', linewidth=2)
axs[6].plot(time, uu_star[0,:],'--r', linewidth=2)
axs[6].grid()
axs[6].set_ylabel('$delta$')
axs[6].set_xlabel('time')
axs[6].set_xlim([-1,Tsim])
axs[6].legend(['MPC', 'OPT'])

#####
axs[7].plot(time, uu_real_mpc[1,:],'g', linewidth=2)
axs[7].plot(time, uu_star[1,:],'--r', linewidth=2)

if u1max < 1.1*np.amax(uu_real_mpc[1,:]): # draw constraints only if active
  axs[7].plot(time, np.ones(Tsim)*u1max, '--g', linewidth=1)
  axs[7].plot(time, np.ones(Tsim)*u1min, '--g', linewidth=1)

axs[7].grid()
axs[7].set_ylabel('$F$')
axs[7].set_xlabel('time')
axs[7].set_xlim([-1,Tsim])
axs[7].legend(['MPC', 'OPT'])

fig.align_ylabels(axs)

plt.show()


#######################################################################
######################## TASK 5: ANIMATION ############################
#######################################################################

time = np.arange(len(tt_hor))*dt

if visu_animation:
    
  fig = plt.figure()
  ax = fig.add_subplot(111, autoscale_on=False, xlim=(min(xx_ref[0,:])-1, max(xx_ref[0,:])+1), ylim=(min(uu_ref[0,:])-1, max(uu_ref)+1))
  ax.grid()
  # no labels
  ax.set_yticklabels([])
  ax.set_xticklabels([])
  ax.title.set_text('Animation of the Trajectory')

  
  line0, = ax.plot([], [], 'o-', lw=2, c='b', label='Optimal')
  line1, = ax.plot([], [], '--', lw=2, c='g', dashes=[2, 2], label='Reference')

  time_template = 't = %.1f s'
  time_text = ax.text(0.05, 0.9, '', transform=ax.transAxes)
  fig.gca().set_aspect('equal', adjustable='box')

  # Subplot
  left, bottom, width, height = [0.64, 0.13, 0.2, 0.2]
  ax2 = fig.add_axes([left, bottom, width, height])
  ax2.xaxis.set_major_locator(MultipleLocator(2))
  ax2.yaxis.set_major_locator(MultipleLocator(0.5))
  ax2.set_xticklabels([])
  

  ax2.grid(which='both')
  ax2.plot(time, xx_reg[3],c='b')
  ax2.plot(time, xx_ref[3], c='g', dashes=[2, 1])
  ax2.title.set_text('psi')

  point1, = ax2.plot([], [], 'o', lw=2, c='b')


  def init():
    line0.set_data([], [])
    line1.set_data([], [])

    point1.set_data([], [])

    time_text.set_text('')
    return line0, line1, time_text, point1


  def animate(i):
    # Trajectory
    thisx0 = [xx_reg[0, i]]
    thisy0 = [xx_reg[1, i]]
    line0.set_data(thisx0, thisy0)

    # Reference
    thisx1 = [xx_ref[0, :]]
    thisy1 = [xx_ref[1, :]]
    line1.set_data(thisx1, thisy1)

    point1.set_data(i*dt, xx_reg[3, i])

    time_text.set_text(time_template % (i*dt))
    return line0, line1, time_text, point1


  ani = animation.FuncAnimation(fig, animate, TT, interval=0.001, blit=True, init_func=init)
  ax.legend(loc="lower left")

  
  plt.show()

