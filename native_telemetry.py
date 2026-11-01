"""Read-only flight instrumentation. SI source values, explicit reference frames."""
import math


def flight_details(state):
    sections=[]
    def group(key,title,note=''):
        section=dict(id=key,title=title,note=note,rows=[]);sections.append(section)
        return section['rows']
    def row(rows,label,value,unit=''):
        if isinstance(value,(tuple,list)):
            for i,part in enumerate(value):row(rows,label+' '+str(i+1),part,unit)
        else:rows.append(dict(label=label,value=value,unit=unit))
    space=state.get('vehicle')=='space';lunar=state.get('scenario')=='planetary'
    frame='ENU locale' if lunar else 'ECI' if space else 'NED locale'
    att=group('attitude','ASSETTO E ROTAZIONE',state.get('attitude_frame','Euler roll / pitch / yaw · corpo rispetto a '+frame))
    for label,value in zip(('Roll','Pitch','Yaw'),state.get('attitude_deg',[])):row(att,label,value,'°')
    for label,value in zip(('p · roll rate','q · pitch rate','r · yaw rate'),state.get('body_rates_rad_s',[])):row(att,label,math.degrees(value),'°/s')
    quat=state.get('attitude_quaternion_body_to_eci',state.get('quaternion_body_to_enu'))
    if quat:
        for label,value in zip(('Quaternion w','Quaternion x','Quaternion y','Quaternion z'),quat):row(att,label,value)
    if 'attitude_error_deg' in state:row(att,'Errore di assetto',state['attitude_error_deg'],'°')
    sas=state.get('sas',{})
    if sas.get('supported'):
        row(att,'SAS','OVERRIDE MANUALE' if sas.get('manual_override') else 'ON' if sas.get('enabled') else 'OFF')
        row(att,'Preset SAS',sas.get('mode'))
        row(att,'Autorità assetto',sas.get('authority'))
        row(att,'Attuatore SAS',sas.get('actuator'))
        row(att,'Limite coppia ruote',sas.get('torque_limit_N_m'),'N·m')
        row(att,'Momento ruote',state.get('wheel_momentum_body_N_m_s'),'N·m·s')
    pos=group('position','POSIZIONE E VELOCITÀ','Stato fisico · '+frame+'. ECI inerziale; NED Nord/Est/Giù; ENU Est/Nord/Su.')
    xyz=state.get('position_enu_m') if lunar else state.get('position_eci_m') if space else state.get('position_ned_m')
    axes=('Est','Nord','Su') if lunar else ('X ECI','Y ECI','Z ECI') if space else ('Nord','Est','Giù')
    for label,value in zip(axes,xyz or []):row(pos,label,value,'m')
    vel=state.get('velocity_enu_m_s') if lunar else state.get('velocity_eci_m_s') if space else state.get('velocity_body_m_s')
    for label,value in zip(('V Est','V Nord','V Su') if lunar else ('Vx ECI','Vy ECI','Vz ECI') if space else ('u corpo','v corpo','w corpo'),vel or []):row(pos,label,value,'m/s')
    row(pos,'Quota',state.get('altitude_m'),'m');row(pos,'Velocità inerziale' if space else 'Velocità',state.get('speed_m_s'),'m/s')
    if 'ground_speed_m_s' in state:row(pos,'Velocità al suolo',state['ground_speed_m_s'],'m/s')
    if space and not lunar and xyz and vel:
        radius=math.sqrt(sum(x*x for x in xyz));vertical=sum(x*y for x,y in zip(xyz,vel))/radius
        row(pos,'Velocità radiale (su)',vertical,'m/s')
    orb=group('orbit','ORBITA E RENDEZVOUS','Elementi osculanti a due corpi. Le quote apsidali negative indicano intersezione con il corpo.')
    elements=state.get('orbital_elements') or {}
    if elements:
        for key,label,unit in [('orbit_type','Regime',''),('conic_type','Conica',''),('semi_major_axis_m','Semiasse maggiore','m'),('eccentricity','Eccentricità',''),('inclination_deg','Inclinazione','°'),('periapsis_altitude_m','Quota pericentro','m'),('apoapsis_altitude_m','Quota apocentro','m'),('period_s','Periodo','s'),('specific_orbital_energy_J_kg','Energia specifica','J/kg')]:row(orb,label,elements.get(key),unit)
        for key,label,unit in [('relative_range_m','Distanza relativa','m'),('relative_speed_m_s','Velocità relativa','m/s')]:
            if key in state:row(orb,label,state[key],unit)
        for key,label,unit in [('relative_position_rtn_m','RTN posizione','m'),('relative_velocity_rtn_m_s','RTN velocità','m/s')]:
            if key in state:row(orb,label,state[key],unit)
    else:row(orb,'Disponibilità','N/A · riferimento locale, nessuna orbita calcolata')
    mech=group('flight','MECCANICA DEL VOLO','Forze e coefficienti del modello attivo; nessuna misura sintetica aggiunta.')
    for key,label,unit in [('mass_kg','Massa','kg'),('load_factor_g','Fattore di carico','g'),('air_relative_speed_m_s','Velocità relativa aria','m/s'),('specific_force_magnitude_m_s2','Forza specifica','m/s²')]:row(mech,label,state.get(key),unit)
    env=state.get('environment',{});aero=state.get('aerodynamics',{})
    sound=env.get('speed_of_sound_m_s');airspeed=state.get('air_relative_speed_m_s')
    if sound and airspeed is not None:row(mech,'Mach',airspeed/sound)
    for key,label,unit in [('angle_of_attack_deg','Incidenza α','°'),('angle_of_sideslip_deg','Deriva β','°'),('lift_coefficient','CL',''),('drag_coefficient','CD',''),('stall_margin_deg','Margine stallo','°'),('stall_state','Stallo','')]:
        if key in aero:row(mech,label,aero[key],unit)
    for key,label,unit in [('dynamic_pressure_Pa','Pressione dinamica','Pa'),('density_kg_m3','Densità','kg/m³'),('temperature_K','Temperatura','K'),('pressure_Pa','Pressione statica','Pa'),('stagnation_point_convective_heat_flux_W_m2','Flusso termico stagnazione','W/m²')]:
        if key in env:row(mech,label,env[key],unit)
    prop=group('propulsion','PROPULSIONE ED ENERGIA')
    for key,label,unit in [('propellant_kg','Propellente','kg'),('propellant_pct','Propellente residuo','%'),('battery_pct','Batteria','%'),('active_stage','Stadio attivo',''),('acs_propellant_kg','Propellente ACS','kg')]:
        if key in state:row(prop,label,state[key],unit)
    for key,label,unit in [('applied_thrust_N','Spinta applicata','N'),('thrust_N','Spinta','N'),('effective_isp_s','Isp effettivo','s'),('fuel_flow_kg_s','Portata carburante','kg/s'),('actual_power_pct','Potenza effettiva','%'),('shaft_power_W','Potenza albero','W')]:
        if key in state.get('propulsion',{}):row(prop,label,state['propulsion'][key],unit)
    for key,label,unit in [('total_thrust_actual_N','Spinta rotori','N'),('motor_speed_actual_rpm','Regime rotore','rpm')]:
        if key in state.get('propulsion_actuators',{}):row(prop,label,state['propulsion_actuators'][key],unit)
    for key,label,unit in [('energy_remaining_Wh','Energia residua','Wh'),('power_draw_W','Assorbimento','W'),('endurance_at_current_power_s','Autonomia corrente','s')]:
        if key in state.get('battery',{}):row(prop,label,state['battery'][key],unit)
    nav=group('navigation','NAVIGAZIONE E COMANDI','Stime dei sensori separate dallo stato fisico. — significa dato non disponibile.')
    estimate=state.get('navigation_estimate') or state.get('relative_navigation_estimate') or {}
    for key,label,unit in [('estimator','Stimatore',''),('frame','Riferimento',''),('altitude_m','Quota stimata','m'),('altitude_sigma_m','Incertezza quota 1σ','m'),('vertical_speed_m_s','Rateo verticale stimato','m/s'),('position_sigma_eci_m','Incertezza ECI 1σ','m'),('position_sigma_m','Incertezza ENU 1σ','m'),('position_sigma_rtn_m','Incertezza RTN 1σ','m'),('gnss_integrity','Integrità GNSS',''),('gnss_age_s','Età fix GNSS','s')]:
        if key in estimate:row(nav,label,estimate[key],unit)
    command=state.get('command',{})
    row(nav,'Modo controllo',command.get('mode'))
    for key,label,unit in [('throttle_pct','Spinta comandata','%'),('roll_deg','Roll comandato','°'),('pitch_deg','Pitch comandato','°'),('yaw_deg','Yaw comandato','°'),('brakes_pct','Freni','%')]:row(nav,label,command.get(key),unit)
    return sections
