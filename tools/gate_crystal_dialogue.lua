-- Prove the Crystal-only dialogue layer is active on Crystal and inactive on
-- Gold, using the real headless mod loader and a ROM-free fixture dataset.
-- Usage: luajit gate_crystal_dialogue.lua <engine_root> <mod_dir> <expectation_json>

local engineRoot, modDir, expectationPath = ...
if not (engineRoot and modDir and expectationPath) then
  io.stderr:write("usage: luajit gate_crystal_dialogue.lua <engine_root> <mod_dir> <expectation_json>\n")
  os.exit(2)
end
package.path = engineRoot .. "/?.lua;" .. engineRoot .. "/?/init.lua;" .. package.path

local T = require("tests.modkit")
local Json = require("src.link.Json")
local GameVersion = require("src.core.GameVersion")
local file = assert(io.open(expectationPath, "rb"))
local expectation = Json.decode(file:read("*a"))
file:close()
assert(type(expectation) == "table" and type(expectation.pointer) == "string"
  and type(expectation.value) == "string", "invalid Crystal gate expectation")

local failures = 0
local function check(condition, message)
  if condition then print("ok - " .. message) return end
  failures = failures + 1
  io.stderr:write("FAIL - " .. message .. "\n")
end

local parent, name = modDir:match("^(.*)[/\\]([^/\\]*)$")
if not parent then parent, name = ".", modDir end
local previous = GameVersion.get()

GameVersion.set("crystal")
local crystal = T.sdk.loadMod(name, { generation = 2, root = parent })
check(#crystal.errors == 0, "Crystal: mod loads with no errors")
check(crystal.data.gen2Text[expectation.pointer] == expectation.value,
  "Crystal: Crystal-only pointer receives its translation")
crystal.release()

GameVersion.set("gold")
local gold = T.sdk.loadMod(name, { generation = 2, root = parent })
check(#gold.errors == 0, "Gold: mod loads with no errors")
check(gold.data.gen2Text[expectation.pointer] == nil,
  "Gold: Crystal-only pointer is not applied")
gold.release()
GameVersion.set(previous)

if failures > 0 then os.exit(1) end
print("all Crystal dialogue gate checks passed")
