CXX ?= c++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Werror -pedantic
BUILD_DIR ?= work/tests
TESTS := $(BUILD_DIR)/transport_test $(BUILD_DIR)/car_parameter_policy_test \
         $(BUILD_DIR)/event_stream_test $(BUILD_DIR)/event_mapping_test \
         $(BUILD_DIR)/offline_service_core_test $(BUILD_DIR)/state_contract_test \
         $(BUILD_DIR)/callback_policy_test $(BUILD_DIR)/control_policy_test \
         $(BUILD_DIR)/deferred_controls_test $(BUILD_DIR)/eq_policy_test \
         $(BUILD_DIR)/external_disk_reset_test

.PHONY: all test test-binder test-device-tree
all: $(TESTS)

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/transport_test: native/mtc_transport.cpp native/transport_test.cpp native/mtc_transport.hpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -pthread native/mtc_transport.cpp native/transport_test.cpp $(LDFLAGS) -o $@

$(BUILD_DIR)/car_parameter_policy_test: native/car_parameter_policy.cpp native/car_parameter_policy_test.cpp native/car_parameter_policy.hpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) native/car_parameter_policy.cpp native/car_parameter_policy_test.cpp $(LDFLAGS) -o $@

$(BUILD_DIR)/event_stream_test: native/event_stream.cpp native/event_stream_test.cpp native/event_stream.hpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) native/event_stream.cpp native/event_stream_test.cpp $(LDFLAGS) -o $@

$(BUILD_DIR)/event_mapping_test: native/event_stream.cpp native/event_mapping.cpp native/event_mapping_test.cpp native/event_stream.hpp native/event_mapping.hpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) native/event_stream.cpp native/event_mapping.cpp native/event_mapping_test.cpp $(LDFLAGS) -o $@

CORE_SOURCES := native/offline_service_core.cpp native/car_parameter_policy.cpp native/event_stream.cpp native/event_mapping.cpp
CORE_HEADERS := native/offline_service_core.hpp native/car_parameter_policy.hpp native/event_stream.hpp native/event_mapping.hpp

$(BUILD_DIR)/offline_service_core_test: $(CORE_SOURCES) $(CORE_HEADERS) native/offline_service_core_test.cpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -pthread $(CORE_SOURCES) native/offline_service_core_test.cpp $(LDFLAGS) -o $@

$(BUILD_DIR)/state_contract_test: $(CORE_SOURCES) $(CORE_HEADERS) native/state_contract_test.cpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -pthread $(CORE_SOURCES) native/state_contract_test.cpp $(LDFLAGS) -o $@

$(BUILD_DIR)/callback_policy_test: $(CORE_SOURCES) $(CORE_HEADERS) native/callback_policy.cpp native/callback_policy.hpp native/callback_policy_test.cpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -pthread $(CORE_SOURCES) native/callback_policy.cpp native/callback_policy_test.cpp $(LDFLAGS) -o $@

$(BUILD_DIR)/control_policy_test: native/control_policy.cpp native/control_policy.hpp native/event_mapping.hpp native/event_stream.hpp native/control_policy_test.cpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) native/control_policy.cpp native/control_policy_test.cpp $(LDFLAGS) -o $@

$(BUILD_DIR)/deferred_controls_test: native/deferred_controls.cpp native/deferred_controls.hpp native/control_policy.cpp native/control_policy.hpp native/event_mapping.hpp native/event_stream.hpp native/deferred_controls_test.cpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) native/control_policy.cpp native/deferred_controls.cpp native/deferred_controls_test.cpp $(LDFLAGS) -o $@

$(BUILD_DIR)/eq_reference.hpp: evidence/malaysk-eq-tables.json scripts/eq_test_fixture.py | $(BUILD_DIR)
	python3 scripts/eq_test_fixture.py $< $@

$(BUILD_DIR)/eq_policy_test: native/eq_policy.cpp native/eq_policy.hpp native/event_mapping.hpp native/event_stream.hpp native/eq_policy_test.cpp $(BUILD_DIR)/eq_reference.hpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -Inative -I$(BUILD_DIR) native/eq_policy.cpp native/eq_policy_test.cpp $(LDFLAGS) -o $@

$(BUILD_DIR)/external_disk_reset_test: native/external_disk_reset.hpp native/external_disk_reset_test.cpp | $(BUILD_DIR)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) native/external_disk_reset_test.cpp $(LDFLAGS) -o $@

test: all
	$(BUILD_DIR)/transport_test
	$(BUILD_DIR)/car_parameter_policy_test
	$(BUILD_DIR)/event_stream_test
	$(BUILD_DIR)/event_mapping_test
	$(BUILD_DIR)/offline_service_core_test
	$(BUILD_DIR)/state_contract_test
	$(BUILD_DIR)/callback_policy_test
	$(BUILD_DIR)/control_policy_test
	$(BUILD_DIR)/deferred_controls_test
	$(BUILD_DIR)/eq_policy_test
	$(BUILD_DIR)/external_disk_reset_test
	python3 scripts/android_packed_relocations_test.py
	python3 scripts/check_vold_bindings_test.py

AIDL ?= aidl
test-binder:
	python3 scripts/check_binder_contract.py --aidl "$(AIDL)" --reference evidence/malaysk-proxy-wire.json --report work/binder-contract-check.json
	python3 scripts/check_binder_contract_test.py --generated work/binder-check --reference evidence/malaysk-proxy-wire.json

test-device-tree:
	python3 scripts/device_tree_profile_test.py
