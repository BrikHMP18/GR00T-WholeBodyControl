#ifndef ONNX_CPU_ENGINE_HPP
#define ONNX_CPU_ENGINE_HPP

#include <algorithm>
#include <iostream>
#include <memory>
#include <numeric>
#include <string>
#include <vector>

#include <onnxruntime_cxx_api.h>

class OnnxCpuSingleIoEngine {
public:
  bool Initialize(const std::string& model_path,
                  const std::string& engine_name,
                  const std::string& expected_input_name,
                  const std::string& expected_output_name,
                  size_t expected_output_dimension = 0) {
    try {
      engine_name_ = engine_name;
      input_tensor_name_ = expected_input_name;
      output_tensor_name_ = expected_output_name;

      env_ = std::make_unique<Ort::Env>(ORT_LOGGING_LEVEL_WARNING, engine_name.c_str());
      Ort::SessionOptions session_options;
      session_options.SetIntraOpNumThreads(1);
      session_options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_EXTENDED);
      session_ = std::make_unique<Ort::Session>(*env_, model_path.c_str(), session_options);

      Ort::AllocatorWithDefaultOptions allocator;
      const auto input_names = ReadNames(true, allocator);
      if (input_names.size() != 1 || input_names[0] != expected_input_name) {
        std::cerr << "✗ " << engine_name << " expects one input tensor named '"
                  << expected_input_name << "'" << std::endl;
        return false;
      }

      const auto output_names = ReadNames(false, allocator);
      if (output_names.size() != 1 || output_names[0] != expected_output_name) {
        std::cerr << "✗ " << engine_name << " expects one output tensor named '"
                  << expected_output_name << "'" << std::endl;
        return false;
      }

      input_shape_ = RuntimeShape(session_->GetInputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape());
      const auto output_shape = RuntimeShape(session_->GetOutputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape());
      input_buffer_.assign(ElementCount(input_shape_), 0.0f);
      output_buffer_.assign(ElementCount(output_shape), 0.0f);

      if (expected_output_dimension > 0 && output_buffer_.size() != expected_output_dimension) {
        std::cerr << "✗ " << engine_name << " output dimension (" << output_buffer_.size()
                  << ") doesn't match expected dimension (" << expected_output_dimension << ")" << std::endl;
        return false;
      }

      initialized_ = true;
      std::cout << "✓ " << engine_name << " ONNX CPU engine initialized successfully!" << std::endl;
      std::cout << "  Model: " << model_path << std::endl;
      std::cout << "  Input dimension: " << input_buffer_.size() << std::endl;
      std::cout << "  Output dimension: " << output_buffer_.size() << std::endl;
      return true;
    } catch (const std::exception& e) {
      std::cerr << "✗ " << engine_name << "::Initialize - Exception: " << e.what() << std::endl;
      Destroy();
      return false;
    }
  }

  bool Run() {
    if (!initialized_ || !session_) {
      std::cerr << "✗ " << engine_name_ << " - ONNX CPU engine not initialized" << std::endl;
      return false;
    }

    auto memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    auto input_tensor = Ort::Value::CreateTensor<float>(
        memory_info, input_buffer_.data(), input_buffer_.size(), input_shape_.data(), input_shape_.size());

    const char* input_names[] = {input_tensor_name_.c_str()};
    const char* output_names[] = {output_tensor_name_.c_str()};
    auto outputs = session_->Run(Ort::RunOptions{nullptr}, input_names, &input_tensor, 1, output_names, 1);

    const auto output_info = outputs[0].GetTensorTypeAndShapeInfo();
    const size_t output_count = output_info.GetElementCount();
    output_buffer_.resize(output_count);
    std::copy_n(outputs[0].GetTensorData<float>(), output_count, output_buffer_.begin());
    return true;
  }

  template<typename T>
  void SetInputData(const T* data, size_t element_count) {
    if (!initialized_) { return; }
    std::copy_n(data, std::min(element_count, input_buffer_.size()), input_buffer_.begin());
  }

  template<typename T>
  void SetInputData(const std::vector<T>& data) {
    SetInputData(data.data(), data.size());
  }

  void Destroy() {
    session_.reset();
    env_.reset();
    initialized_ = false;
  }

  bool IsInitialized() const { return initialized_; }
  size_t GetInputDimension() const { return input_buffer_.size(); }
  size_t GetOutputDimension() const { return output_buffer_.size(); }
  const std::string& GetInputTensorName() const { return input_tensor_name_; }
  const std::string& GetOutputTensorName() const { return output_tensor_name_; }
  std::vector<std::string> GetInputTensorNames() const { return {input_tensor_name_}; }
  std::vector<std::string> GetOutputTensorNames() const { return {output_tensor_name_}; }
  std::vector<float>& GetInputBuffer() { return input_buffer_; }
  std::vector<float>& GetOutputBuffer() { return output_buffer_; }

private:
  static std::vector<int64_t> RuntimeShape(std::vector<int64_t> shape) {
    for (auto& dim : shape) {
      if (dim <= 0) { dim = 1; }
    }
    return shape;
  }

  static size_t ElementCount(const std::vector<int64_t>& shape) {
    return std::accumulate(shape.begin(), shape.end(), static_cast<size_t>(1),
                           [](size_t product, int64_t dim) {
                             return product * static_cast<size_t>(std::max<int64_t>(dim, 1));
                           });
  }

  std::vector<std::string> ReadNames(bool inputs, Ort::AllocatorWithDefaultOptions& allocator) const {
    std::vector<std::string> names;
    const size_t count = inputs ? session_->GetInputCount() : session_->GetOutputCount();
    for (size_t i = 0; i < count; ++i) {
      auto name = inputs ? session_->GetInputNameAllocated(i, allocator)
                         : session_->GetOutputNameAllocated(i, allocator);
      names.emplace_back(name.get());
    }
    return names;
  }

  std::string engine_name_;
  std::unique_ptr<Ort::Env> env_;
  std::unique_ptr<Ort::Session> session_;
  std::string input_tensor_name_;
  std::string output_tensor_name_;
  std::vector<int64_t> input_shape_;
  std::vector<float> input_buffer_;
  std::vector<float> output_buffer_;
  bool initialized_ = false;
};

#endif
