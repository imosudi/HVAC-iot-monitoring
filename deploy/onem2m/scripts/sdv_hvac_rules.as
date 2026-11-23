;;
;; ACMEScript: SDV Cabin HVAC Closed-Loop Rule Engine (Replaces Node-RED IPE)
;; Evaluates incoming SCD30 telemetry <m2m:cin> creations and dispatches
;; closed-loop PWM & discrete actuator directives to /sdv-cse/<vehicle-id>/commands.
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
                (setq rh (get-json-attribute scd30 "humidity_pct"))
                (setq car-id (get-json-attribute payload "car_id"))
                (setq ts (get-json-attribute payload "timestamp_unix_s"))

                ;; Determine target PWM duty cycle & fan state from CO2 / Temperature
                (setq target-pwm 25)
                (setq fan-on "true")
                (if (>= co2 1500)
                    (setq target-pwm 100)
                    (if (>= co2 1000)
                        (setq target-pwm 75)
                        (if (>= co2 800)
                            (setq target-pwm 50)
                            (if (< temp 19.0)
                                (progn
                                    (setq target-pwm 0)
                                    (setq fan-on "false"))))))

                ;; Discrete thermal & humidity actuator flags
                (setq heater-on (if (< temp 18.0) "true" "false"))
                (setq ac-on (if (> temp 30.0) "true" "false"))
                (setq hum-on (if (< rh 30.0) "true" "false"))
                (setq dehum-on (if (> rh 60.0) "true" "false"))

                ;; Construct command payload & dispatch <m2m:cin> to /sdv-cse/<car-id>/commands
                (setq cmd-con (string-append
                    "{\"target_pwm\":" (to-string target-pwm)
                    ",\"mode\":\"AUTOMATIC\""
                    ",\"timestamp_unix_s\":" (to-string ts)
                    ",\"source_entity\":\"ACMEScripts\""
                    ",\"actions\":{"
                    "\"fan\":" fan-on
                    ",\"ac\":" ac-on
                    ",\"heater\":" heater-on
                    ",\"humidifier\":" hum-on
                    ",\"dehumidifier\":" dehum-on
                    "}}"))
                (setq cin-body (string-append
                    "{\"m2m:cin\":{\"cnf\":\"application/json:0\",\"con\":"
                    (to-json-string cmd-con)
                    "}}"))
                (setq target-cnt (string-append "/id-sdv/sdv-cse/" car-id "/commands"))
                (create-resource "CAdmin" target-cnt cin-body)
                (log-info (string-append "[ACMEScripts] " car-id " CO2=" (to-string co2) " T=" (to-string temp) " RH=" (to-string rh) " -> PWM=" (to-string target-pwm) "% heater=" heater-on " dehum=" dehum-on)))))
)
