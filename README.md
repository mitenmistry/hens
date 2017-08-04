# HENS
##### Miten Mistry and Ruth Misener.

### Project Description
This project implements an algorithm that lower bounds a given mixed-integer nonlinear programming (MINLP) Synheat instance. 
The algorithm models the MINLP formulation as a mixed-integer linear programming relaxation and iteratively tightens by adding cutting planes for convex functions and breakpoints for piecewise approximations.

The following paper describes the method.

- Mistry, M., Misener, R. 2016. Optimising heat exchanger network synthesis using convexity properties of the logarithmic mean temperature difference. Computers & Chemical Engineering. 94, 1-17. 

### Prerequisites
- Python 3.5.2
- Pyomo 5.0.1
- PyLatex 1.0.0 (optional)
- Gurobi

### Usage
To find out how to use the code, run from terminal:

```shell
cd <directory>
python iterative.py -h
```
where directory is one of:

- adaptive_model_mixer,
- beta_adaptive_model_mixer.

These two directories contain the two algorithm mentioned in the associated paper.

#### Adding your own datafile
Put it in the `datafiles` directory and give it the extension `.dat`.
The contents of the datafile should be similar to that of those already in the `datafiles` directory.
Assuming that the new datafile is called `example.dat`, running the following should work.
```shell
cd adaptive_model_mixer
python iterative.py example anyAlphaNumericThingCanGoHere
```
