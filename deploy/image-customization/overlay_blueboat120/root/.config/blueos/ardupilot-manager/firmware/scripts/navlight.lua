-- This scripts is used to control Blue Robotics`s NavLight on the Blue Boat

local LIGHT_PIN = 18
gpio:pinMode(LIGHT_PIN, 1)

local MODES = {
    "MANU",
    "ACRO",
    "STEE",
    "HOLD",
    "LOIT",
    "FOLL",
    "SIMP",
    "DOCK",
    "AUTO",
    "RTL",
    "SMAR",
    "GUID",
    "DSRM"
}

local MODE_MAPPING = {
    [0] = "MANU",
    [1] = "ACRO",
    [3] = "STEE",
    [4] = "HOLD",
    [5] = "LOIT",
    [6] = "FOLL",
    [7] = "SIMP",
    [8] = "DOCK",
    [10] = "AUTO",
    [11] = "RTL",
    [12] = "SMAR",
    [15] = "GUID",
    [16] = "INIT"
}

local PARAM_TABLE_KEY = 70
local PARAM_TABLE_PREFIX = "NL_"
assert(param:add_table(PARAM_TABLE_KEY, "NL_", 52), "could not add param table")

-- bind a parameter to a variable
function bind_param(name)
    local p = Parameter()
    assert(p:init(name), string.format("could not find %s parameter", name))
    return p
end

-- add a parameter and bind it to a variable
function bind_add_param(name, idx, default_value)
    assert(param:add_param(PARAM_TABLE_KEY, idx, name, default_value), string.format("could not add param %s", name))
    return bind_param(PARAM_TABLE_PREFIX .. name)
end

local PARAMS_IDLE = {} -- Dictionary for interval parameters
local PARAMS_ON_TMH = {} -- Dictionary for high time parameters
local PARAMS_OFF_TM = {} -- Dictionary for low time parameters
local PARAMS_BLINKS = {} -- Dictionary for times parameters
local param_idx = 1

local DEFAULTS = {
    ["MANU"] = {500, 20, 150, 1},
    ["ACRO"] = {500, 20, 150, 1},
    ["STEE"] = {500, 20, 150, 1},
    ["HOLD"] = {2000, 20, 150, 1}, -- Arm
    ["LOIT"] = {0, 0, 0, 0}, -- Large blink value to simulate constant light
    ["FOLL"] = {0, 0, 0, 0}, -- Large blink value to simulate constant light
    ["SIMP"] = {500, 20, 150, 1},
    ["DOCK"] = {1000, 20, 150, 3},
    ["AUTO"] = {1000, 20, 150, 3},
    ["RTL"] = {1000, 20, 150, 3},
    ["SMAR"] = {1000, 20, 150, 3},
    ["GUID"] = {1000, 20, 150, 3},
    ["DSRM"] = {2000, 20, 150, 1} -- Disarm
}
for _, mode in ipairs(MODES) do
    local defaults = DEFAULTS[mode]
    PARAMS_IDLE[mode] = bind_add_param(mode .. "_IDLE", param_idx, defaults[1])
    PARAMS_ON_TMH[mode] = bind_add_param(mode .. "_ON_TM", param_idx + 1, defaults[2]) -- High time parameters
    PARAMS_OFF_TM[mode] = bind_add_param(mode .. "_OFF_TM", param_idx + 2, defaults[3]) -- Low time parameters
    PARAMS_BLINKS[mode] = bind_add_param(mode .. "_BLINKS", param_idx + 3, defaults[4])
    param_idx = param_idx + 4
end

local last_blink = 0
local blink_counter = 0
local is_light_on_tm = false

function update() -- this is the loop which periodically runs
    local now = millis():tofloat()
    local mode_num = vehicle:get_mode()
    local mode = MODE_MAPPING[mode_num]

    if mode == nil then
        -- gcs:send_text(0, string.format("Unrecognized mode number: %s", mode_num))
        mode = "DSRM" -- or another default mode
    end

    -- check if the vehicle is disarmed
    if not arming:is_armed() then
        mode = "DSRM"
    end

    local interval = PARAMS_IDLE[mode]:get()
    local high = PARAMS_ON_TMH[mode]:get() -- High time parameter
    local low = PARAMS_OFF_TM[mode]:get() -- Low time parameter
    local times = PARAMS_BLINKS[mode]:get()

    if interval == 0 then -- Special case, light always on
        if not is_light_on_tm then
            gpio:write(LIGHT_PIN,1)
            is_light_on_tm = true
        end
        return update, 50 -- reschedules
    end

    -- Check if it's time to start a new cycle
    if blink_counter >= times and now - last_blink >= interval then
        blink_counter = 0
        is_light_on_tm = false
    end

    -- Check if it's time to toggle the light
    if blink_counter < times and now - last_blink >= (is_light_on_tm and high or low) then
        gpio:toggle(LIGHT_PIN)
        is_light_on_tm = not is_light_on_tm
        if is_light_on_tm then
            gpio:write(LIGHT_PIN, 1)
        else
            gpio:write(LIGHT_PIN, 0)
        end
        last_blink = now
        if not is_light_on_tm then -- Increment the counter when the light turns off
            blink_counter = blink_counter + 1
        end
    end

    -- Turn off the light at the end of the cycle
    if blink_counter >= times and is_light_on_tm then
        gpio:write(LIGHT_PIN, 0)
        is_light_on_tm = false
    end

    return update, 50 -- reschedules
end

return update() -- run immediately before starting to reschedule