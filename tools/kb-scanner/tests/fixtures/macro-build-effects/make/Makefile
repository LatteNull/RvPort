include flags.mk
NAME = USE_AVX2=1
DEFINES = $(PREFIX) $(NAME)
kernel.o: kernel.cpp
	$(CXX) $(DEFINES) -c $< -o $@
