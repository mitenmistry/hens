# Author: Miten Mistry
#         Department of Computing, Imperial College London

import os, sys, bisect

from argparse import ArgumentParser, RawTextHelpFormatter

from pprint import pprint

from pyomo.core.base.numvalue import value

from .model_declarations.model_builder import create_model
from .model_declarations.helper_functions import two_point_generator, three_point_generator, lmtd_inv_beta
from .constants import *

stream_tangent_points = {}
cu_tangent_points     = {}
hu_tangent_points     = {}

stream_q_beta_breakpoints = {}
cu_q_beta_breakpoints     = {}
hu_q_beta_breakpoints     = {}

stream_area_q_beta_breakpoints = {}
cu_area_q_beta_breakpoints     = {}
hu_area_q_beta_breakpoints     = {}

th_breakpoints  = {}
thx_breakpoints = {}
tc_breakpoints  = {}
tcx_breakpoints = {}

def create_output_dir(root, model, append):
    model_dir  = root + os.sep + model
    append_dir = model_dir + os.sep + append
    iterations_dir = append_dir + os.sep + iterations
    log_dir = iterations_dir + os.sep + logs
    instance_dir = iterations_dir + os.sep + instances

    if not os.path.exists(model_dir):
        os.makedirs(model_dir)

    if not os.path.exists(append_dir):
        os.makedirs(append_dir)

    if not os.path.exists(iterations_dir):
        os.makedirs(iterations_dir)

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)

    return {\
        model_folder     : model_dir,\
        append_folder    : append_dir,\
        iterations_folder: iterations_dir,\
        logs_folder      : log_dir,\
        instances_folder : instance_dir,\
    }

def initialise_parser():
    parser = ArgumentParser()
    parser.add_argument('model', help='The model you wish to run e.g. model1 for datafile: ../datafiles/model1.dat')
    parser.add_argument('run_name', help='The name of the run you are running the results will be placed in a directory with this name')
    parser.add_argument('-i', '--print-instance', help='print instance of final run', action='store_true')
    parser.add_argument('-t', '--num-threads', type=int, help='Number of cpu cores used. If this value is larger than the number of cores available the maximum number of cores will be used. Must be a positive integer.')
    parser.add_argument('-c', '--cont', help='Get continuation message. Requires feedback after the first 50 iterations.', action='store_true')
    parser.add_argument('-w', '--weaken', help='If set doesn\'t add breakpoints for inactive balancing constraints.', action='store_true')
    parser.add_argument('-a', '--absolute', help='Use absolute error', action='store_true')
    parser.add_argument('--lmtd-beta-eps', help='Max absolute lmtd error, a negative value will terminate when no new tangents are placed. DEFAULT=0.0001', type=float)
    parser.add_argument('--bal-eps', help='Max absolute error for balancing bilinearities. DEFAULT=0.0001', type=float)
    parser.add_argument('--q-beta-eps', help='Max absolute error for area bilinearities. DEFAULT=0.0001', type=float)
    parser.add_argument('--area-beta-eps', help='Max absolute error for area betas. DEFAULT=0.0001', type=float)
    parser.add_argument('-e', '--all-error', help='Max absolute error for all approximations, a negative value will terminate when no new tangents are placed. DEFAULT=0.0001', type=float)
    parser.add_argument('-m', '--tighten-tol', help='Tightens tolerances. Sets: IntFeasTol = 1e-9, FeasibilityTol = 1e-9, OptimalityTol = 1e-9', action='store_true')
    parser.add_argument('--IntFeasTol', type=float, help='Sets integer feasibility tolerance. Min=1e-9. Default=1e-5. Max=1e-2. Overridden by m flag.')
    parser.add_argument('--FeasibilityTol', type=float, help='Sets primal feasibility tolerance. Min=1e-9. Default=1e-6. Max=1e-2. Overridden by m flag.')
    parser.add_argument('--OptimalityTol', type=float, help='Sets dual feasibility tolerance. Min=1e-9. Default=1e-6. Max=1e-2. Overridden by m flag.')
    parser.add_argument('--MarkowitzTol', type=float, help='Sets threshold pivoting tolerance. Min=1e-4. Default=0.0078125. Max=0.999. Overridden by m flag.')
    return parser

def validate_and_assign_args(args):
    if args.num_threads:
        if args.num_threads <= 0:
            raise ValueError('The number of threads must be positive')

def add_initial_th_breakpoints(instance):
    for i in instance.HP:
        for k in instance.ST:
            global th_breakpoints
            th_breakpoints[i,k] = [m for m in instance.Th_breakpoints[i,k]]

def add_initial_thx_breakpoints(instance):
    for i in instance.HP:
        for j in instance.CP:
            for k in instance.ST:
                global thx_breakpoints
                thx_breakpoints[i,j,k] = [m for m in instance.Thx_breakpoints[i,j,k]]

def add_initial_tc_breakpoints(instance):
    for j in instance.CP:
        for k in instance.K_Take_First_Stage:
            global tc_breakpoints
            tc_breakpoints[j,k] = [m for m in instance.Tc_breakpoints[j,k]]

def add_initial_tcx_breakpoints(instance):
    for i in instance.HP:
        for j in instance.CP:
            for k in instance.ST:
                global tcx_breakpoints
                tcx_breakpoints[i,j,k] = [m for m in instance.Tcx_breakpoints[i,j,k]]

def add_initial_q_beta_breakpoints(instance):
    for i in instance.HP:
        for j in instance.CP:
            for k in instance.ST:
                global stream_q_beta_breakpoints
                stream_q_beta_breakpoints[i,j,k] = [m for m in instance.Q_beta_breakpoints[i,j,k]]

def add_initial_q_cu_beta_breakpoints(instance):
    for i in instance.HP:
        global cu_q_beta_breakpoints
        cu_q_beta_breakpoints[i] = [m for m in instance.Q_cu_beta_breakpoints[i]]

def add_initial_q_hu_beta_breakpoints(instance):
    for j in instance.CP:
        global hu_q_beta_breakpoints
        hu_q_beta_breakpoints[j] = [m for m in instance.Q_hu_beta_breakpoints[j]]

def add_initial_stream_tangent_points(instance):
    for i in instance.HP:
        for j in instance.CP:
            for k in instance.ST:
                global stream_tangent_points
                stream_tangent_points[i,j,k] = three_point_generator(default_tangent_weights[stream_hx], instance.dt[i,j,k].bounds)

def add_initial_cu_tangent_points(instance):
    for i in instance.HP:
        global cu_tangent_points
        cu_tangent_points[i] = two_point_generator(default_tangent_weights[cu_hx], instance.dt_cu[i].bounds)

def add_initial_hu_tangent_points(instance):
    for j in instance.CP:
        global hu_tangent_points
        hu_tangent_points[j] = two_point_generator(default_tangent_weights[hu_hx], instance.dt_hu[j].bounds)

def add_initial_stream_area_q_beta_breakpoints(instance):
    for i in instance.HP:
        for j in instance.CP:
            for k in instance.ST:
                global stream_area_q_beta_breakpoints
                stream_area_q_beta_breakpoints[i,j,k] = [m for m in instance.Area_beta_q_breakpoints[i,j,k]]

def add_initial_cu_area_q_beta_breakpoints(instance):
    for i in instance.HP:
        global cu_area_q_beta_breakpoints
        cu_area_q_beta_breakpoints[i] = [m for m in instance.Area_beta_q_cu_breakpoints[i]]

def add_initial_hu_area_q_beta_breakpoints(instance):
    for j in instance.CP:
        global hu_area_q_beta_breakpoints
        hu_area_q_beta_breakpoints[j] = [m for m in instance.Area_beta_q_hu_breakpoints[j]]

def declare_th_breakpoints(model, i, k):
    global th_breakpoints
    return th_breakpoints[i,k]

def declare_thx_breakpoints(model, i, j, k):
    global thx_breakpoints
    return thx_breakpoints[i,j,k]

def declare_tc_breakpoints(model, j, k):
    global tc_breakpoints
    return tc_breakpoints[j,k]

def declare_tcx_breakpoints(model, i, j, k):
    global tcx_breakpoints
    return tcx_breakpoints[i,j,k]

def declare_stream_tangent_points(model, i, j, k):
    global stream_tangent_points
    return stream_tangent_points[i,j,k]

def declare_cu_tangent_points(model, i):
    global cu_tangent_points
    return cu_tangent_points[i]

def declare_hu_tangent_points(model, j):
    global hu_tangent_points
    return hu_tangent_points[j]

def declare_stream_q_beta_breakpoints(model, i, j, k):
    global stream_q_beta_breakpoints
    return stream_q_beta_breakpoints[i,j,k]

def declare_cu_q_beta_breakpoints(model, i):
    global cu_q_beta_breakpoints
    return cu_q_beta_breakpoints[i]

def declare_hu_q_beta_breakpoints(model, j):
    global hu_q_beta_breakpoints
    return hu_q_beta_breakpoints[j]

def declare_stream_area_q_beta_breakpoints(model, i, j, k):
    global stream_area_q_beta_breakpoints
    return stream_area_q_beta_breakpoints[i,j,k]

def declare_cu_area_q_beta_breakpoints(model, i):
    global cu_area_q_beta_breakpoints
    return cu_area_q_beta_breakpoints[i]

def declare_hu_area_q_beta_breakpoints(model, j):
    global hu_area_q_beta_breakpoints
    return hu_area_q_beta_breakpoints[j]

def initialise_hx_model(datafile):
    model = create_model()
    instance = model.create_instance(datafile)

    add_initial_th_breakpoints(instance)
    add_initial_thx_breakpoints(instance)
    add_initial_tc_breakpoints(instance)
    add_initial_tcx_breakpoints(instance)

    add_initial_q_beta_breakpoints(instance)
    add_initial_q_cu_beta_breakpoints(instance)
    add_initial_q_hu_beta_breakpoints(instance)

    add_initial_stream_tangent_points(instance)
    add_initial_cu_tangent_points(instance)
    add_initial_hu_tangent_points(instance)

    add_initial_stream_area_q_beta_breakpoints(instance)
    add_initial_cu_area_q_beta_breakpoints(instance)
    add_initial_hu_area_q_beta_breakpoints(instance)

    model.Th_breakpoints.initialize  = declare_th_breakpoints
    model.Thx_breakpoints.initialize = declare_thx_breakpoints
    model.Tc_breakpoints.initialize  = declare_tc_breakpoints
    model.Tcx_breakpoints.initialize = declare_tcx_breakpoints

    model.Reclmtd_beta_gradient_points.initialize    = declare_stream_tangent_points
    model.Reclmtd_cu_beta_gradient_points.initialize = declare_cu_tangent_points
    model.Reclmtd_hu_beta_gradient_points.initialize = declare_hu_tangent_points

    model.Q_beta_breakpoints.initialize = declare_stream_q_beta_breakpoints
    model.Q_cu_beta_breakpoints.initialize = declare_cu_q_beta_breakpoints
    model.Q_hu_beta_breakpoints.initialize = declare_hu_q_beta_breakpoints

    model.Area_beta_q_breakpoints.initialize = declare_stream_area_q_beta_breakpoints
    model.Area_beta_q_cu_breakpoints.initialize = declare_cu_area_q_beta_breakpoints
    model.Area_beta_q_hu_breakpoints.initialize = declare_hu_area_q_beta_breakpoints

    return model

def get_active_hx(instance):
    active_hx = {
        stream_hx    : [],
        cu_hx        : [],
        hu_hx        : []
    }
    inactive_hx = {
        stream_hx    : [],
        cu_hx        : [],
        hu_hx        : []
    }
    for index in instance.z:
        if value(instance.z[index]) >= active_lb:
            active_hx[stream_hx].append(index)
        else:
            inactive_hx[stream_hx].append(index)

    for index in instance.z_cu:
        if value(instance.z_cu[index]) >= active_lb:
            active_hx[cu_hx].append(index)
        else:
            inactive_hx[cu_hx].append(index)

    for index in instance.z_hu:
        if value(instance.z_hu[index]) >= active_lb:
            active_hx[hu_hx].append(index)
        else:
            inactive_hx[hu_hx].append(index)

    return active_hx, inactive_hx

def get_new_tangent_points(instance, active_hx):
    new_tangents = {
        stream_hx    : {},
        cu_hx        : {},
        hu_hx        : {}
    }
    for index in active_hx[stream_hx]:
        x_index = index
        y_index = (index[0], index[1], index[2]+1)
        x = value(instance.dt[x_index])
        y = value(instance.dt[y_index])
        new_tangent_point = (x,y) if x >= y else (y,x)
        new_tangents[stream_hx][index] = new_tangent_point

    for index in active_hx[cu_hx]:
        x = value(instance.dt_cu[index])
        new_tangents[cu_hx][index] = x

    for index in active_hx[hu_hx]:
        x = value(instance.dt_hu[index])
        new_tangents[hu_hx][index] = x

    return new_tangents

def get_new_balancing_breakpoints(instance, active_hx, inactive_hx, weaken):
    new_th_breakpoints = {}
    new_thx_breakpoints = {}
    new_tc_breakpoints = {}
    new_tcx_breakpoints = {}

    # active_th_indices = list(set(map(lambda (i,j,k): (i,k), active_hx[stream_hx])))
    # active_tc_indices = list(set(map(lambda (i,j,k): (j, k+1), active_hx[stream_hx])))

    active_th_indices = list(set((i,k) for i,_,k in active_hx[stream_hx]))
    active_tc_indices = list(set((j,k+1) for _,j,k in active_hx[stream_hx]))

    for index in active_th_indices:
        breakpoint = instance.th[index].value
        if breakpoint not in th_breakpoints[index]:
            bisect.insort(th_breakpoints[index], breakpoint)
            new_th_breakpoints[index] = breakpoint

    for index in active_hx[stream_hx]:
        breakpoint = instance.thx[index].value
        if breakpoint not in thx_breakpoints[index]:
            bisect.insort(thx_breakpoints[index], breakpoint)
            new_thx_breakpoints[index] = [breakpoint]

    for index in active_tc_indices:
        breakpoint = instance.tc[index].value
        if breakpoint not in tc_breakpoints[index]:
            bisect.insort(tc_breakpoints[index], breakpoint)
            new_tc_breakpoints[index] = breakpoint

    for index in active_hx[stream_hx]:
        breakpoint = instance.tcx[index].value
        if breakpoint not in tcx_breakpoints[index]:
            bisect.insort(tcx_breakpoints[index], breakpoint)
            new_tcx_breakpoints[index] = [breakpoint]

    if not weaken:
        for index in inactive_hx[stream_hx]:
            if instance.bh_out[index].value > 0.000001:
                breakpoint = instance.thx[index].value
                if breakpoint not in thx_breakpoints[index]:
                    bisect.insort(thx_breakpoints[index], breakpoint)
                    new_thx_breakpoints[index] = breakpoint

            if instance.bc_out[index].value > 0.000001:
                breakpoint = instance.tcx[index].value
                if breakpoint not in tcx_breakpoints[index]:
                    bisect.insort(tcx_breakpoints[index], breakpoint)
                    new_tcx_breakpoints[index] = breakpoint

    new_balancing_breakpoints = {}
    if not len(new_th_breakpoints) == 0:
        new_balancing_breakpoints['th'] = new_th_breakpoints

    if not len(new_thx_breakpoints) == 0:
        new_balancing_breakpoints['thx'] = new_thx_breakpoints

    if not len(new_tc_breakpoints) == 0:
        new_balancing_breakpoints['tc'] = new_tc_breakpoints

    if not len(new_tcx_breakpoints) == 0:
        new_balancing_breakpoints['tcx'] = new_tcx_breakpoints

    return new_balancing_breakpoints

def get_new_q_beta_breakpoints(instance, active_hx):
    new_stream_q_beta_breakpoints = {}
    new_cu_q_beta_breakpoints = {}
    new_hu_q_beta_breakpoints = {}

    for index in active_hx[stream_hx]:
        breakpoint = instance.q[index].value
        if breakpoint not in stream_q_beta_breakpoints[index]:
            bisect.insort(stream_q_beta_breakpoints[index], breakpoint)
            new_stream_q_beta_breakpoints[index] = breakpoint

    for index in active_hx[cu_hx]:
        breakpoint = instance.q_cu[index].value
        if breakpoint not in cu_q_beta_breakpoints[index]:
            bisect.insort(cu_q_beta_breakpoints[index], breakpoint)
            new_cu_q_beta_breakpoints[index] = breakpoint

    for index in active_hx[hu_hx]:
        breakpoint = instance.q_hu[index].value
        if breakpoint not in hu_q_beta_breakpoints[index]:
            bisect.insort(hu_q_beta_breakpoints[index], breakpoint)
            new_hu_q_beta_breakpoints[index] = breakpoint

    new_q_beta_breakpoints = {}
    if not len(new_stream_q_beta_breakpoints) == 0:
        new_q_beta_breakpoints[stream_hx] = new_stream_q_beta_breakpoints

    if not len(new_cu_q_beta_breakpoints) == 0:
        new_q_beta_breakpoints[cu_hx] = new_cu_q_beta_breakpoints

    if not len(new_hu_q_beta_breakpoints) == 0:
        new_q_beta_breakpoints[hu_hx] = new_hu_q_beta_breakpoints

    return new_q_beta_breakpoints

def get_new_area_q_beta_breakpoints(instance, active_hx):
    new_stream_area_q_beta_breakpoints = {}
    new_cu_area_q_beta_breakpoints = {}
    new_hu_area_q_beta_breakpoints = {}

    for index in active_hx[stream_hx]:
        breakpoint = instance.q_beta[index].value
        if breakpoint not in stream_area_q_beta_breakpoints[index]:
            bisect.insort(stream_area_q_beta_breakpoints[index], breakpoint)
            new_stream_area_q_beta_breakpoints[index] = breakpoint

    for index in active_hx[cu_hx]:
        breakpoint = instance.q_cu_beta[index].value
        if breakpoint not in cu_area_q_beta_breakpoints[index]:
            bisect.insort(cu_area_q_beta_breakpoints[index], breakpoint)
            new_cu_area_q_beta_breakpoints[index] = breakpoint

    for index in active_hx[hu_hx]:
        breakpoint = instance.q_hu_beta[index].value
        if breakpoint not in hu_area_q_beta_breakpoints[index]:
            bisect.insort(hu_area_q_beta_breakpoints[index], breakpoint)
            new_hu_area_q_beta_breakpoints[index] = breakpoint

    new_area_q_beta_breakpoints = {}
    if not len(new_stream_area_q_beta_breakpoints) == 0:
        new_area_q_beta_breakpoints[stream_hx] = new_stream_area_q_beta_breakpoints

    if not len(new_cu_area_q_beta_breakpoints) == 0:
        new_area_q_beta_breakpoints[cu_hx] = new_cu_area_q_beta_breakpoints

    if not len(new_hu_area_q_beta_breakpoints) == 0:
        new_area_q_beta_breakpoints[hu_hx] = new_hu_area_q_beta_breakpoints

    return new_area_q_beta_breakpoints

def add_new_tangent_points(new_tangent_points):
    added_tangents = {
    }
    for index, tangent_point in new_tangent_points[stream_hx].items():
        if not tangent_point in stream_tangent_points[index]:
            if not stream_hx in added_tangents:
                added_tangents[stream_hx] = {}
            stream_tangent_points[index].append(tangent_point)
            added_tangents[stream_hx][index] = [tangent_point]
            if not tangent_point[0] == tangent_point[1]:
                stream_tangent_points[index].append((tangent_point[1], tangent_point[0]))
                added_tangents[stream_hx][index].append((tangent_point[1], tangent_point[0]))

    for index, tangent_point in new_tangent_points[cu_hx].items():
        if not tangent_point in cu_tangent_points[index]:
            if not cu_hx in added_tangents:
                added_tangents[cu_hx] = {}
            cu_tangent_points[index].append(tangent_point)
            added_tangents[cu_hx][index] = [tangent_point]

    for index, tangent_point in new_tangent_points[hu_hx].items():
        if not tangent_point in hu_tangent_points[index]:
            if not hu_hx in added_tangents:
                added_tangents[hu_hx] = {}
            hu_tangent_points[index].append(tangent_point)
            added_tangents[hu_hx][index] = [tangent_point]

    return added_tangents

def calculate_reclmtd_beta_error(x, y, beta, reclmtd_beta_estimate):
    reclmtd_beta_correct = lmtd_inv_beta(x, y, beta)
    error = reclmtd_beta_correct - reclmtd_beta_estimate
    rel_error = error/reclmtd_beta_correct
    abs_error = error
    return {\
        absolute_error: abs_error,\
        relative_error: rel_error,\
    }

def calculate_stream_reclmtd_beta_error(instance, i, j, k):
    dt_hot  = instance.dt[(i,j,k)].value
    dt_cold = instance.dt[(i,j,k+1)].value
    beta = instance.Beta
    reclmtd_beta_estimate = instance.reclmtd_beta[(i,j,k)].value
    return calculate_reclmtd_beta_error(dt_hot, dt_cold, beta, reclmtd_beta_estimate)

def calculate_cu_reclmtd_beta_error(instance, i):
    dt  = instance.dt_cu[i].value
    dt2 = instance.Th_out[i] - instance.T_cu_in
    beta = instance.Beta
    reclmtd_beta_estimate = instance.reclmtd_cu_beta[i].value
    return calculate_reclmtd_beta_error(dt, dt2, beta, reclmtd_beta_estimate)

def calculate_hu_reclmtd_beta_error(instance, j):
    dt  = instance.dt_hu[j].value
    dt2 = instance.T_hu_in - instance.Tc_out[j]
    beta = instance.Beta
    reclmtd_beta_estimate = instance.reclmtd_hu_beta[j].value
    return calculate_reclmtd_beta_error(dt, dt2, beta, reclmtd_beta_estimate)

def calculate_q_beta_errors(q, beta, q_beta_estimate):
    q_beta_correct = pow(q, beta)
    error = q_beta_correct - q_beta_estimate
    rel_error = error/q_beta_correct
    abs_error = error
    return {\
        absolute_error: abs_error,\
        relative_error: rel_error,\
    }

def calculate_stream_q_beta_error(instance, i, j, k):
    q = instance.q[i,j,k].value
    beta = instance.Beta
    q_beta_estimate = instance.q_beta[i,j,k].value
    return calculate_q_beta_errors(q, beta, q_beta_estimate)

def calculate_cu_q_beta_error(instance, i):
    q_cu = instance.q_cu[i].value
    beta = instance.Beta
    q_cu_beta_estimate = instance.q_cu_beta[i].value
    return calculate_q_beta_errors(q_cu, beta, q_cu_beta_estimate)

def calculate_hu_q_beta_error(instance, j):
    q_hu = instance.q_hu[j].value
    beta = instance.Beta
    q_hu_beta_estimate = instance.q_hu_beta[j].value
    return calculate_q_beta_errors(q_hu, beta, q_hu_beta_estimate)

def calculate_area_beta_errors(q_beta, reclmtd_beta, u_beta, area_beta_estimate):
    area_beta_correct = u_beta*q_beta*reclmtd_beta
    error = area_beta_correct - area_beta_estimate
    rel_error = error/area_beta_correct
    abs_error = error
    return {\
        absolute_error: abs_error,\
        relative_error: rel_error,\
    }

def calculate_stream_area_beta_error(instance, i, j, k):
    q_beta = instance.q_beta[i,j,k].value
    reclmtd_beta = instance.reclmtd_beta[i,j,k].value
    u_beta = instance.U_beta[i,j]
    area_beta_estimate = instance.area_beta[i,j,k].value
    return calculate_area_beta_errors(q_beta, reclmtd_beta, u_beta, area_beta_estimate)

def calculate_cu_area_beta_error(instance, i):
    q_beta = instance.q_cu_beta[i].value
    reclmtd_beta = instance.reclmtd_cu_beta[i].value
    u_beta = instance.U_cu_beta[i]
    area_beta_estimate = instance.area_cu_beta[i].value
    return calculate_area_beta_errors(q_beta, reclmtd_beta, u_beta, area_beta_estimate)

def calculate_hu_area_beta_error(instance, j):
    q_beta = instance.q_hu_beta[j].value
    reclmtd_beta = instance.reclmtd_hu_beta[j].value
    u_beta = instance.U_hu_beta[j]
    area_beta_estimate = instance.area_hu_beta[j].value
    return calculate_area_beta_errors(q_beta, reclmtd_beta, u_beta, area_beta_estimate)

def calculate_bilinear_errors(f, t, bilinear_estimate):
    bilinear_correct = f*t
    if bilinear_correct < 0.000001:
        return {\
            absolute_error: 0,\
            relative_error: 0,\
        }
    error = bilinear_estimate - bilinear_correct
    rel_error = error/bilinear_correct if not t == 0 else 0
    abs_error = error
    return {\
        absolute_error: abs_error,\
        relative_error: rel_error,\
    }

def calculate_bhin(instance, i, j, k):
    f = instance.fh[i,j,k].value
    t = instance.th[i,k].value
    bhin = instance.bh_in[i,j,k].value
    return calculate_bilinear_errors(f, t, bhin)

def calculate_bhout(instance, i, j, k):
    f = instance.fh[i,j,k].value
    t = instance.thx[i,j,k].value
    bhout = instance.bh_out[i,j,k].value
    return calculate_bilinear_errors(f, t, bhout)

def calculate_bcin(instance, i, j, k):
    f = instance.fc[i,j,k].value
    t = instance.tc[j,k+1].value
    bcin = instance.bc_in[i,j,k].value
    return calculate_bilinear_errors(f, t, bcin)

def calculate_bcout(instance, i, j, k):
    f = instance.fc[i,j,k].value
    t = instance.tcx[i,j,k].value
    bcout = instance.bc_out[i,j,k].value
    return calculate_bilinear_errors(f, t, bcout)

def get_all_points():
    return {\
        stream_hx: {\
            tangent_points: stream_tangent_points,\
            q_beta_points: stream_q_beta_breakpoints,\
            area_q_beta_points: stream_area_q_beta_breakpoints,\
            th_points: th_breakpoints,\
            thx_points: thx_breakpoints,\
            tc_points: tc_breakpoints,\
            tcx_points: tcx_breakpoints,\
        },\
        cu_hx: {\
            tangent_points: cu_tangent_points,\
            q_beta_points: cu_q_beta_breakpoints,\
            area_q_beta_points: cu_area_q_beta_breakpoints,\
        },\
        hu_hx: {\
            tangent_points: hu_tangent_points,\
            q_beta_points: hu_q_beta_breakpoints,\
            area_q_beta_points: hu_area_q_beta_breakpoints,\
        },\
    }

def summarise_errors(instance, active_hx, inactive_hx, weaken):
    errors = {}

    errors[stream_hx] = {}
    errors[cu_hx]     = {}
    errors[hu_hx]     = {}

    errors[stream_hx][reclmtd_beta_error] = {}
    errors[cu_hx][reclmtd_beta_error]     = {}
    errors[hu_hx][reclmtd_beta_error]     = {}

    errors[stream_hx][q_beta_error] = {}
    errors[cu_hx][q_beta_error]     = {}
    errors[hu_hx][q_beta_error]     = {}

    errors[stream_hx][area_beta_error] = {}
    errors[cu_hx][area_beta_error]     = {}
    errors[hu_hx][area_beta_error]     = {}

    errors[stream_hx][bhin_error]  = {}
    errors[stream_hx][bhout_error] = {}
    errors[stream_hx][bcin_error]  = {}
    errors[stream_hx][bcout_error] = {}

    for (i,j,k) in active_hx[stream_hx]:
        errors[stream_hx][reclmtd_beta_error][i,j,k] = calculate_stream_reclmtd_beta_error(instance, i, j, k)
        errors[stream_hx][q_beta_error][i,j,k] = calculate_stream_q_beta_error(instance, i, j, k)
        errors[stream_hx][area_beta_error][i,j,k] = calculate_stream_area_beta_error(instance, i, j, k)
        errors[stream_hx][bhin_error][i,j,k] = calculate_bhin(instance, i, j, k)
        errors[stream_hx][bhout_error][i,j,k] = calculate_bhout(instance, i, j, k)
        errors[stream_hx][bcin_error][i,j,k] = calculate_bcin(instance, i, j, k)
        errors[stream_hx][bcout_error][i,j,k] = calculate_bcout(instance, i, j, k)

    if not weaken:
        for (i,j,k) in inactive_hx[stream_hx]:
            errors[stream_hx][bhout_error][i,j,k] = calculate_bhout(instance, i, j, k)
            errors[stream_hx][bcout_error][i,j,k] = calculate_bcout(instance, i, j, k)

    for i in active_hx[cu_hx]:
        errors[cu_hx][reclmtd_beta_error][i] = calculate_cu_reclmtd_beta_error(instance, i)
        errors[cu_hx][q_beta_error][i] = calculate_cu_q_beta_error(instance, i)
        errors[cu_hx][area_beta_error][i] = calculate_cu_area_beta_error(instance, i)

    for j in active_hx[hu_hx]:
        errors[hu_hx][reclmtd_beta_error][j] = calculate_hu_reclmtd_beta_error(instance, j)
        errors[hu_hx][q_beta_error][j] = calculate_hu_q_beta_error(instance, j)
        errors[hu_hx][area_beta_error][j] = calculate_hu_area_beta_error(instance, j)

    return errors

def get_max_errors(errors, active_hx, inactive_hx, weaken):

    max_errors = {
        balancing_ref: {
            absolute_error: -1, \
            relative_error: -1, \
        },
        q_beta_ref: {
            absolute_error: -1, \
            relative_error: -1, \
        },
        lmtd_beta_ref: {
            absolute_error: -1, \
            relative_error: -1, \
        },
        area_beta_ref: {
            absolute_error: -1, \
            relative_error: -1, \
        },
    }

    for (i,j,k) in active_hx[stream_hx]:
        max_bilinear_error_abs = max( \
            errors[stream_hx][bhin_error][i,j,k][absolute_error], \
            errors[stream_hx][bhout_error][i,j,k][absolute_error], \
            errors[stream_hx][bcin_error][i,j,k][absolute_error], \
            errors[stream_hx][bcout_error][i,j,k][absolute_error], \
        )

        max_bilinear_error_rel = max( \
                abs(errors[stream_hx][bhin_error][i,j,k][relative_error]), \
                abs(errors[stream_hx][bhout_error][i,j,k][relative_error]), \
                abs(errors[stream_hx][bcin_error][i,j,k][relative_error]), \
                abs(errors[stream_hx][bcout_error][i,j,k][relative_error]), \
            )

        if max_errors[balancing_ref][absolute_error] < max_bilinear_error_abs:
            max_errors[balancing_ref][absolute_error] = max_bilinear_error_abs

        if max_errors[balancing_ref][relative_error] < max_bilinear_error_rel:
            max_errors[balancing_ref][relative_error] = max_bilinear_error_rel

    if not weaken:
        for (i,j,k) in inactive_hx[stream_hx]:
            max_bilinear_error_abs = max( \
                errors[stream_hx][bhout_error][i,j,k][absolute_error], \
                errors[stream_hx][bcout_error][i,j,k][absolute_error], \
            )

            max_bilinear_error_rel = max( \
                    abs(errors[stream_hx][bhout_error][i,j,k][relative_error]), \
                    abs(errors[stream_hx][bcout_error][i,j,k][relative_error]), \
                )

            if max_errors[balancing_ref][absolute_error] < max_bilinear_error_abs:
                max_errors[balancing_ref][absolute_error] = max_bilinear_error_abs

            if max_errors[balancing_ref][relative_error] < max_bilinear_error_rel:
                max_errors[balancing_ref][relative_error] = max_bilinear_error_rel

    for check_set in [stream_hx, cu_hx, hu_hx]:
        for index in active_hx[check_set]:
            if max_errors[q_beta_ref][absolute_error] < errors[check_set][q_beta_error][index][absolute_error]:
                max_errors[q_beta_ref][absolute_error] = errors[check_set][q_beta_error][index][absolute_error]

            if max_errors[q_beta_ref][relative_error] < errors[check_set][q_beta_error][index][relative_error]:
                max_errors[q_beta_ref][relative_error] = errors[check_set][q_beta_error][index][relative_error]

            if max_errors[lmtd_beta_ref][absolute_error] < errors[check_set][reclmtd_beta_error][index][absolute_error]:
                max_errors[lmtd_beta_ref][absolute_error] = errors[check_set][reclmtd_beta_error][index][absolute_error]

            if max_errors[lmtd_beta_ref][relative_error] < errors[check_set][reclmtd_beta_error][index][relative_error]:
                max_errors[lmtd_beta_ref][relative_error] = errors[check_set][reclmtd_beta_error][index][relative_error]

            if max_errors[area_beta_ref][absolute_error] < errors[check_set][area_beta_error][index][absolute_error]:
                max_errors[area_beta_ref][absolute_error] = errors[check_set][area_beta_error][index][absolute_error]

            if max_errors[area_beta_ref][relative_error] < errors[check_set][area_beta_error][index][relative_error]:
                max_errors[area_beta_ref][relative_error] = errors[check_set][area_beta_error][index][relative_error]

    return max_errors
