CXX ?= c++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Werror -pedantic
BUILD_DIR ?= work/tests
TESTS := $(BUILD_DIR)/transport_test $(BUILD_DIR)/car_parameter_policy_test \
         $(BUILD_DIR)/event_stream_test $(BUILD_DIR)/event_mapping_test

.PHONY: all test
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

test: all
	$(BUILD_DIR)/transport_test
	$(BUILD_DIR)/car_parameter_policy_test
	$(BUILD_DIR)/event_stream_test
	$(BUILD_DIR)/event_mapping_test
