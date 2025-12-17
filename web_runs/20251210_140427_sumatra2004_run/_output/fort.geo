  
 --------------------------------------------
 Physics Parameters:
 -------------------
    gravity:   9.8100000000000005     
    density water:   1025.0000000000000     
    density air:   1.1499999999999999     
    ambient pressure:   101300.00000000000     
    earth_radius:   6367500.0000000000     
    coordinate_system:           2
    sea_level:   0.0000000000000000     
  
    coriolis_forcing: F
    theta_0:   0.0000000000000000     
    friction_forcing: T
    manning_coefficient:   2.5000000000000001E-002
    friction_depth:   1000000.0000000000     
  
    dry_tolerance:   1.0000000000000000E-003
  
 --------------------------------------------
 Refinement Control Parameters:
 ------------------------------
    wave_tolerance:  0.10000000000000001     
    speed_tolerance:
    Variable dt Refinement Ratios: T
 
  
 --------------------------------------------
 SETDTOPO:
 -------------
    num dtopo files =            1
    fname:/Users/jackprewitt/Desktop/Fall_2025/MAE330/Tsunami/web_runs/20251210_140427_sumatra2004_run/dtopo_user_fault.tt3                                     
    topo type:           3
  
 --------------------------------------------
 SETTOPO:
 ---------
    mtopofiles =            1
    
    /Users/jackprewitt/Desktop/Fall_2025/MAE330/Tsunami/web_runs/20251210_140427_sumatra2004_run/topo/topo_m81p694_m58p930_28p516_44p652_etopo1_c1.tt3    
   itopotype =            3
   mx =         1366   x = (  -81.683333333333337      ,  -58.933333333334247      )
   my =          969   y = (   28.516666666666669      ,   44.649999999999359      )
   dx, dy (meters/degrees) =    1.6666666666666000E-002   1.6666666666666000E-002
  
   Ranking of topography files  finest to coarsest:            1           2
  
  
 --------------------------------------------
 SETQINIT:
 -------------
   qinit_type = 0, no perturbation
  
 --------------------------------------------
 Multilayer Parameters:
 ----------------------
    check_richardson: T
    richardson_tolerance:  0.94999999999999996     
    eigen_method:           4
    inundation_method:           2
    dry_tolerance:   1.0000000000000000E-003
