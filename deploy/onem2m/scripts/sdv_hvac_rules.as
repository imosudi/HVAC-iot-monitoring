;;
;; ACMEScript: SDV Cabin HVAC Closed-Loop Rule Engine (Replaces Node-RED IPE)
;; Evaluates incoming SCD30 telemetry <m2m:cin> creations and dispatches
;; closed-loop PWM directives to /sdv-cse/<vehicle-id>/commands.
;;

@name sdv_hvac_rules
@description Evaluates SCD30 CO2/Temperature/Humidity thresholds and triggers closed-loop HVAC actuation
@onNotification

;; Extract vehicle container path and JSON payload from notification
(setq con (get-json-attribute (notification-resource) "m2m:cin/con"))
(if (not (is-nil con))
    (progn
        (setq payload (json-to-string-or-map con))
        (setq scd30 (get-json-attribute payload "scd30"))
        (if (not (is-nil scd30))
            (progn
                (setq co2 (get-json-attribute scd30 "co2_ppm"))
                (setq temp (get-json-attribute scd30 "temperature_c"))
                (setq car-id (get-json-attribute payload "car_id"))
                ;; Determine target PWM duty cycle from SCD30 CO2 concentration
                (setq target-pwm 25)
                (if (>= co2 1500)
                    (setq target-pwm 100)
                    (if (>= co2 1000)
                        (setq target-pwm 75)
                        (if (>= co2 800)
                            (setq target-pwm 50)
                            (if (< temp 19.0)
                                (setq target-pwm 0)))))
                (log-info (string-append "[ACMEScripts] " car-id " CO2=" (to-string co2) " ppm -> target_pwm=" (to-string target-pwm) "%")))))
)

